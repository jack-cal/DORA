"""On-demand ordinary P2P availability checks; no node, wallet or mining actor.

Each probe owns only its short-lived client socket. No chain database, wallet,
RPC credentials, incoming listener, service restart or continuous scan is used.
An identity handshake is not full chain validation or a network-wide census.
"""
from __future__ import annotations

import argparse
import asyncio
from concurrent.futures import ThreadPoolExecutor
import ipaddress
import json
import math
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import threading
import time
from .windows_tk import prepare_tk
prepare_tk()
import tkinter as tk
from tkinter import ttk

from .i18n import LANGUAGES, Translator, load_language, save_language, set_translator, tr
from . import __version__
from .network_settings import _atomic_json, default_directory
from .peer import _endpoint
from .peerd import endpoint
from .profiles import NETWORK_NAMES, get_network
from .primitives import hash_to_display
from .wire import (DISCOVERY_PROTOCOL_VERSION, IPV6_PROTOCOL_VERSION, PROTOCOL_VERSION, PeerDisconnected, ProtocolError,
                   Version, decode_version, encode_version, read_frame, write_frame)
from .vertical_dialogs import messagebox
from .vertical_text import VerticalLabel, VerticalButton, VerticalCheckbutton, VerticalTreeview


SETTINGS_NAME = 'monitor-settings.json'
MAX_DNS_WORKERS = 8
_DNS_SLOTS = threading.BoundedSemaphore(MAX_DNS_WORKERS)


def monitor_directory():
    local = os.environ.get('LOCALAPPDATA')
    current = ((Path(local)/'SUMUWW' if local else Path.home()/'.sumuww')/'monitor').resolve()
    legacy = ((Path(local)/'DORA' if local else Path.home()/'.dora')/'monitor').resolve()
    return current if current.exists() or not legacy.exists() else legacy


def normalize_peers(peers, *, allow_internet=False, allow_lan=False):
    if type(allow_internet) is not bool or type(allow_lan) is not bool:
        raise ValueError('Connection permission flags must be bools')
    if not isinstance(peers,(list,tuple)):
        raise ValueError('Monitored peers must be a list')
    result=[]
    for value in peers:
        host,port=endpoint(value,allow_zero=False,allow_internet=allow_internet,allow_lan=allow_lan)
        if host.endswith('.onion'):
            raise ValueError('The node monitor supports direct IPv4 connections only')
        formatted=f'[{host}]:{port}' if ':' in host else f'{host}:{port}'
        if formatted not in result:
            result.append(formatted)
    return result


def saved_sumuww_peers(directory,*,network='dora'):
    """Read public contact JSON only, never the node DB, wallet or RPC token."""
    directory=Path(directory).expanduser().resolve()
    profile=get_network(network)
    result={'peers':[],'allow_internet':False,'allow_lan':False,'error':None}
    def read(name):
        path=directory/name
        if not path.exists():return None
        if path.is_symlink():raise ValueError('Invalid saved peer list')
        return json.loads(path.read_text(encoding='utf-8'))
    try:
        settings=read('network-settings.json')
        if settings is not None:
            if not isinstance(settings,dict) or set(settings)!={'schema_version','listen','peers','allow_internet','allow_lan'} or type(settings['schema_version']) is not int or settings['schema_version']!=1:
                raise ValueError('Invalid saved peer list')
            result['peers']=normalize_peers(settings['peers'],allow_internet=settings['allow_internet'],allow_lan=settings['allow_lan'])
            result['allow_internet'],result['allow_lan']=settings['allow_internet'],settings['allow_lan']
    except (OSError,ValueError,TypeError,UnicodeError):
        result['error']='Some saved node addresses could not be loaded'
    try:
        cache=read('node.sqlite.peers.json')
        if cache is not None:
            if not isinstance(cache,dict) or set(cache)!={'version','network','genesis','peers'} or type(cache['version']) is not int or cache['version']!=1 or cache['network']!=profile.profile_id or cache['genesis']!=profile.genesis.block_hash().hex() or not isinstance(cache['peers'],list):
                raise ValueError('Invalid saved peer list')
            entries=[]
            for entry in cache['peers']:
                if not isinstance(entry,dict) or set(entry)!={'host','port','last_success'} or type(entry['last_success']) not in (float,int) or not math.isfinite(entry['last_success']) or entry['last_success']<=0 or type(entry['port']) is not int:
                    raise ValueError('Invalid saved peer list')
                entries.append(entry)
            for entry in sorted(entries,key=lambda item:item['last_success'],reverse=True):
                address=(f"[{entry['host']}]:{entry['port']}" if ":" in entry["host"] else f"{entry['host']}:{entry['port']}")
                normalized=normalize_peers([address],allow_internet=True,allow_lan=True)[0]
                if normalized not in result['peers']:
                    result['peers'].append(normalized)
                    host=normalized.rsplit(':',1)[0].strip('[]')
                    ip=ipaddress.ip_address(host)
                    result['allow_internet']=result['allow_internet'] or ip.is_global
                    result['allow_lan']=result['allow_lan'] or not ip.is_global and not ip.is_loopback
    except (OSError,ValueError,TypeError,UnicodeError):
        result['error']='Some saved node addresses could not be loaded'
    return result


async def _resolve_name(host,port):
    """Resolve without attaching an uncancellable DNS job to the event loop.

    OS DNS calls cannot reliably be interrupted. At most eight daemon workers
    may remain in those calls after a query times out; they do not delay query
    completion or application exit. A saturated resolver fails promptly rather
    than creating more workers or an unbounded job queue.
    """
    if not _DNS_SLOTS.acquire(blocking=False):
        raise OSError('DNS resolver capacity is temporarily full')
    loop=asyncio.get_running_loop()
    future=loop.create_future()

    def deliver(answers,error):
        if future.done():return
        if error is None:future.set_result(answers)
        else:future.set_exception(error)

    def worker():
        answers,error=None,None
        try:
            answers=socket.getaddrinfo(host,port,family=socket.AF_UNSPEC,type=socket.SOCK_STREAM)
        except Exception:
            error=OSError('DNS resolution failed')
        finally:
            _DNS_SLOTS.release()
        try:
            loop.call_soon_threadsafe(deliver,answers,error)
        except RuntimeError:
            # The query deadline may already have closed its private loop.
            pass

    try:
        threading.Thread(target=worker,name='sumuww-monitor-dns',daemon=True).start()
    except Exception:
        _DNS_SLOTS.release()
        future.cancel()
        raise OSError('DNS resolver could not start')
    return await future


async def _resolve(target,allow_internet,allow_lan):
    host,port=target
    try:
        ipaddress.ip_address(host)
    except ValueError:
        answers=await _resolve_name(host,port)
        allowed=[]
        for answer in answers[:64]:
            try:
                checked=_endpoint(answer[4][0],port,allow_internet=allow_internet,allow_lan=allow_lan)
            except ValueError:
                continue
            if checked not in allowed:
                allowed.append(checked)
            if len(allowed)==8:
                break
        if not allowed:
            raise OSError('No permitted DNS result')
        return allowed
    return [_endpoint(host,port,allow_internet=allow_internet,allow_lan=allow_lan)]


async def probe_peer(address,*,network='dora',allow_internet=False,allow_lan=False,timeout=5):
    """Verify identity and its acknowledgement without joining the peer set.

    The monitor deliberately never sends its own verack. The remote node stays
    in its handshake state, so this check cannot add an unsynchronized ready
    session that pauses ordinary mining. Announced tips remain unverified.
    """
    if type(timeout) not in (int,float) or not math.isfinite(timeout) or not .05<=timeout<=30:
        raise ValueError('Monitor deadline must be finite and between 0.05 and 30 seconds')
    normalized=normalize_peers([address],allow_internet=allow_internet,allow_lan=allow_lan)[0]
    target=endpoint(normalized,allow_zero=False,allow_internet=allow_internet,allow_lan=allow_lan)
    profile=get_network(network)
    started=time.monotonic()
    result={'endpoint':normalized,'status':'unreachable','reason':'Connection failed',
            'protocol':None,'peer_id':None,'advertised_tip':None,'claimed_height':None,'latency_ms':None,
            'discovered_peers':[],'full_chain_validated':False}

    async def session(protocol):
        writer=None
        legacy_candidate=False
        try:
            addresses=await _resolve(target,allow_internet,allow_lan)
            last=None
            for numeric in addresses:
                try:
                    reader,writer=await asyncio.wait_for(asyncio.open_connection(*numeric,family=socket.AF_INET6 if ':' in numeric[0] else socket.AF_INET,limit=64*1024),timeout=timeout/len(addresses))
                    break
                except OSError as error:
                    last=error
            else:
                raise last or OSError('Connection failed')
            frame=await read_frame(reader,timeout,magic=profile.message_magic)
            if frame.command!='version':
                raise ProtocolError('Expected version')
            remote=decode_version(frame.payload)
            if remote.genesis!=profile.genesis.block_hash() or remote.profile!=profile.profile_id:
                result.update(status='wrong_network',reason='Network or genesis mismatch')
                return False
            if remote.protocol not in (PROTOCOL_VERSION,DISCOVERY_PROTOCOL_VERSION,IPV6_PROTOCOL_VERSION):
                result.update(status='protocol_error',reason='Unsupported protocol')
                return False
            legacy_candidate=protocol==DISCOVERY_PROTOCOL_VERSION and remote.protocol==PROTOCOL_VERSION
            negotiated=max(protocol,remote.protocol)
            nonce=secrets.randbits(64)
            if nonce==remote.nonce:
                nonce^=1
            own=Version(negotiated,profile.genesis.block_hash(),nonce,profile.profile_id,profile.genesis.block_hash())
            await write_frame(writer,'version',encode_version(own),timeout,magic=profile.message_magic)
            frame=await read_frame(reader,timeout,magic=profile.message_magic)
            if frame.command!='verack' or frame.payload:
                raise ProtocolError('Expected empty verack')
            result.update(status='reachable',reason='SMW identity handshake passed',protocol=negotiated,
                          peer_id=f'{remote.nonce:016x}',advertised_tip=hash_to_display(remote.tip),latency_ms=round((time.monotonic()-started)*1000,1))
            return False
        except PeerDisconnected:
            return legacy_candidate and result['status']!='reachable'
        except OSError:
            return legacy_candidate and result['status']!='reachable'
        except ProtocolError as error:
            if result['status']!='reachable':
                if str(error)=='Network magic mismatch':
                    result.update(status='wrong_network',reason='Network or genesis mismatch')
                elif 'timed out' in str(error):
                    result.update(status='unreachable',reason='No response before deadline')
                else:
                    result.update(status='protocol_error',reason='Invalid protocol response')
            return False
        finally:
            if writer is not None:
                writer.close()
                try:
                    await asyncio.wait_for(writer.wait_closed(),timeout=.5)
                except (OSError,TimeoutError,asyncio.CancelledError):
                    pass

    async def complete():
        if await session(DISCOVERY_PROTOCOL_VERSION):
            await session(PROTOCOL_VERSION)

    try:
        await asyncio.wait_for(complete(),timeout=timeout)
    except TimeoutError:
        if result['status']!='reachable':
            result['reason']='No response before deadline'
    except OSError:
        if result['status']!='reachable':
            result['reason']='Connection failed'
    return result


class NodeMonitor:
    def __init__(self,directory,*,network='dora',peers=None,allow_internet=False,allow_lan=False,timeout=5,saved_node_directory=None):
        self.directory=Path(directory).expanduser().resolve()
        self.network=get_network(network).name
        self.allow_internet,self.allow_lan=allow_internet,allow_lan
        self.timeout=timeout
        if peers is None:
            path=self.directory/SETTINGS_NAME
            if path.exists():
                value=json.loads(path.read_text(encoding='utf-8'))
                if not isinstance(value,dict) or set(value)!={'schema_version','peers','allow_internet','allow_lan'} or type(value['schema_version']) is not int or value['schema_version']!=1:
                    raise ValueError('Invalid monitor settings')
                peers=value['peers']
                self.allow_internet,self.allow_lan=value['allow_internet'],value['allow_lan']
            else:
                peers=[]
        self.peers=normalize_peers(peers,allow_internet=self.allow_internet,allow_lan=self.allow_lan)
        self.results=[]
        self._cancel=threading.Event()
        self._executor=ThreadPoolExecutor(max_workers=1,thread_name_prefix='sumuww-node-check')
        self.pending=None
        self.closed=False
        self.saved_node_directory=Path(saved_node_directory).resolve() if saved_node_directory is not None else None
        self.load_error=None
        if self.saved_node_directory is not None:self.load_saved()

    def load_saved(self):
        if self.closed or self.pending is not None and not self.pending.done():
            raise RuntimeError('Wait for the current node check to finish')
        if self.saved_node_directory is None:return self.peers
        saved=saved_sumuww_peers(self.saved_node_directory,network=self.network)
        known=list(self.peers)
        for peer in saved['peers']:
            if peer not in known:known.append(peer)
        self.peers=known
        self.allow_internet=self.allow_internet or saved['allow_internet']
        self.allow_lan=self.allow_lan or saved['allow_lan']
        self.load_error=saved['error']
        return self.peers

    def configure(self,peers,*,allow_internet=False,allow_lan=False):
        if self.closed or self.pending is not None and not self.pending.done():
            raise RuntimeError('Wait for the current node check to finish')
        normalized=normalize_peers(peers,allow_internet=allow_internet,allow_lan=allow_lan)
        _atomic_json(self.directory/SETTINGS_NAME,{'schema_version':1,'peers':normalized,'allow_internet':allow_internet,'allow_lan':allow_lan})
        self.peers,self.allow_internet,self.allow_lan=normalized,allow_internet,allow_lan

    def check(self):
        if self.closed or self.pending is not None and not self.pending.done():
            raise RuntimeError('Wait for the current node check to finish')
        self._cancel.clear()
        self.pending=self._executor.submit(asyncio.run,self._check())
        return self.pending

    async def _check(self):
        async def all_results():
            return await asyncio.gather(*(probe_peer(peer,network=self.network,allow_internet=self.allow_internet,
                                                    allow_lan=self.allow_lan,timeout=self.timeout) for peer in self.peers))
        task=asyncio.create_task(all_results())
        while not task.done():
            if self._cancel.is_set():
                task.cancel()
                await asyncio.gather(task,return_exceptions=True)
                return []
            await asyncio.sleep(.05)
        self.results=await task
        known=list(self.peers)
        for result in self.results:
            if result['status']=='reachable':
                for address in result['discovered_peers']:
                    if address not in known:
                        known.append(address)
        self.peers=known
        return self.results

    def close(self):
        self.closed=True
        self._cancel.set()
        self._executor.shutdown(wait=False,cancel_futures=True)


class NodeManagerApp:
    """Retain the executable entry name; this screen only checks other nodes."""
    def __init__(self,root,monitor,*,result_file=None,close_after_check=False):
        self.root,self.monitor=root,monitor
        self._future=None
        self._closing=False
        self._sumuww_process=None
        self._result_file=Path(result_file).expanduser().resolve() if result_file is not None else None
        self._close_after_check=bool(close_after_check)
        self._reported=False
        self._texts=[]
        self._language_path=monitor.directory/'ui-language.json'
        self._translator=Translator(load_language(self._language_path))
        set_translator(self._translator)
        root._sumuww_translator=self._translator
        self._reflow_job=None
        self._tick_job=None
        self._icon_job=None
        self._destroyed=False
        root.title(str(tr('SMW Node Monitor')))
        root.geometry('1100x600')
        root.minsize(960,540)
        root.protocol('WM_DELETE_WINDOW',self._close)
        assets=Path(__file__).resolve().parent.parent/'assets'
        try:
            self._icon=tk.PhotoImage(master=root,file=str(assets/'sumuww_window_icon.png'))
            root.iconphoto(True,self._icon)
            if os.name=='nt':root.iconbitmap(str(assets/'sumuww.ico'))
            if os.name=='nt':
                from .windows_icon import install_taskbar_icon
                self._icon_job=root.after_idle(lambda: install_taskbar_icon(root,assets/'sumuww.ico'))
        except tk.TclError:pass
        self._build()
        self._apply_language()
        self._tick_job=root.after(100,self._tick)

    def _text(self,factory,parent,key,**options):
        factory={ttk.Label:VerticalLabel,ttk.Button:VerticalButton,
                 ttk.Checkbutton:VerticalCheckbutton}.get(factory,factory)
        options.setdefault('vertical_inline',80)
        widget=factory(parent,text=str(tr(key)),**options)
        self._texts.append((widget,key))
        return widget

    def _build(self):
        shell=ttk.Frame(self.root)
        shell.pack(fill='both',expand=True)
        self._canvas=tk.Canvas(shell,highlightthickness=0,
                               background=ttk.Style(self.root).lookup('TFrame','background'))
        scrollbar=ttk.Scrollbar(shell,orient='vertical',command=self._canvas.yview)
        scrollbar.pack(side='right',fill='y')
        self._canvas.pack(side='left',fill='both',expand=True)
        self._canvas.configure(yscrollcommand=scrollbar.set)
        frame=self._body=ttk.Frame(self._canvas,padding=18)
        self._body_window=self._canvas.create_window(0,0,window=frame,anchor='nw')
        self._canvas.bind('<Configure>',self._resize_content)
        frame.bind('<Configure>',self._content_changed)
        self.root.bind('<MouseWheel>',self._scroll_content,add='+')
        self.root.bind('<Destroy>',self._disposed,add='+')
        frame.columnconfigure(0,weight=1)
        self._header=ttk.Frame(frame)
        self._header.grid(row=0,column=0,columnspan=2,sticky='ew',pady=(0,10))
        self._header.columnconfigure(1,weight=1)
        self._heading=self._text(ttk.Label,self._header,'SMW Node Monitor',font=('Segoe UI',18))
        self.language=tk.StringVar(value=dict(LANGUAGES)[self._translator.language])
        language=self._language_box=ttk.Combobox(self._header,textvariable=self.language,values=[name for _,name in LANGUAGES],state='readonly',width=22)
        language.bind('<<ComboboxSelected>>',self._change_language)
        self._intro_label=self._text(ttk.Label,self._header,'Checks known nodes only when requested. Does not host, mine, restart or control SMW.',wraplength=1020)
        self._peer_row=ttk.Frame(frame)
        self._peer_row.grid(row=2,column=0,columnspan=2,sticky='ew',pady=(0,8))
        self._peer_row.columnconfigure(1,weight=1)
        self._peer_caption=self._text(ttk.Label,self._peer_row,'Known node addresses')
        self.peers=tk.StringVar(value=', '.join(self.monitor.peers))
        self.peer_entry=ttk.Entry(self._peer_row,textvariable=self.peers)
        controls=self._controls=ttk.Frame(frame)
        controls.grid(row=4,column=0,columnspan=2,sticky='ew')
        self._control_rows=[]
        self.internet=tk.BooleanVar(value=self.monitor.allow_internet)
        self.lan=tk.BooleanVar(value=self.monitor.allow_lan)
        internet=self._text(ttk.Checkbutton,controls,'Allow internet connections',variable=self.internet)
        lan=self._text(ttk.Checkbutton,controls,'Allow LAN connections',variable=self.lan)
        self.check_button=self._text(ttk.Button,controls,'Check nodes',command=self._check)
        self.load_button=self._text(ttk.Button,controls,'Load saved SMW peers',command=self._load_saved)
        self.open_button=self._text(ttk.Button,controls,'Open SMW',command=self._open_smw)
        self._control_widgets=(internet,lan,self.check_button,self.load_button,self.open_button)
        self.status=tk.StringVar()
        self._status_label=VerticalLabel(frame,textvariable=self.status,wraplength=1020,vertical_inline=65)
        self._status_label.grid(row=5,column=0,columnspan=2,sticky='ew',pady=10)
        columns=('endpoint','peer_id','status','tip','latency','reason')
        table_frame=ttk.Frame(frame)
        table_frame.grid(row=6,column=0,columnspan=2,sticky='nsew')
        table_frame.columnconfigure(0,weight=1);table_frame.rowconfigure(0,weight=1)
        self.table=VerticalTreeview(table_frame,columns=columns,show='headings',height=8)
        for key,width in zip(columns,(220,155,115,180,80,250)):
            self.table.column(key,width=width,minwidth=70,stretch=True)
        self.table.grid(row=0,column=0,sticky='nsew')
        scrollbar=ttk.Scrollbar(table_frame,orient='horizontal',command=self.table.xview)
        scrollbar.grid(row=1,column=0,sticky='ew');self.table.configure(xscrollcommand=scrollbar.set)
        vertical=ttk.Scrollbar(table_frame,orient='vertical',command=self.table.yview)
        vertical.grid(row=0,column=1,sticky='ns');self.table.configure(yscrollcommand=vertical.set)
        self._notes=ttk.Frame(frame)
        self._notes.grid(row=7,column=0,columnspan=2,sticky='ew',pady=(12,0))
        self._note_labels=(
            self._text(ttk.Label,self._notes,'A successful handshake confirms a reachable SMW peer, not its full chain, mining power or every node worldwide. Advertised tips are unverified claims.',wraplength=1020),
            self._text(ttk.Label,self._notes,'No response may mean an offline node, changed address, firewall, full connection slots or a network problem.',wraplength=1020))
        self.status.set(str(tr('Ready for an on-demand check')))
        for variable in (self.peers,self.internet,self.lan):
            variable.trace_add('write',self._inputs_changed)

    def _inputs_changed(self,*_arguments):
        if self._future is None and self.monitor.results:
            self.monitor.results=[]
            for item in self.table.get_children():self.table.delete(item)
            self.status.set(str(tr('Ready for an on-demand check')))

    def _disposed(self,event):
        if event.widget is self.root:
            self._destroyed=True
            if self._reflow_job is not None:
                self.root.after_cancel(self._reflow_job)
                self._reflow_job=None
            if self._tick_job is not None:
                self.root.after_cancel(self._tick_job)
                self._tick_job=None
            if self._icon_job is not None:
                self.root.after_cancel(self._icon_job)
                self._icon_job=None

    def _resize_content(self,event):
        self._canvas.itemconfigure(self._body_window,width=event.width)
        self._schedule_reflow()

    def _content_changed(self,_event=None):
        self._canvas.configure(scrollregion=self._canvas.bbox('all'))
        self._schedule_reflow()

    def _schedule_reflow(self):
        if not self._destroyed and self._reflow_job is None:
            self._reflow_job=self.root.after_idle(self._reflow)

    def _reflow(self):
        self._reflow_job=None
        if self._destroyed:return
        width=max(1,self._body.winfo_width()-36)
        vertical=self._translator.language=='mn-Mong'
        row=column=used=0
        for widget in self._control_widgets:
            needed=widget.winfo_reqwidth()+12
            if column and used+needed>width:
                row+=1;column=used=0
            if row==len(self._control_rows):
                self._control_rows.append(ttk.Frame(self._controls))
            row_frame=self._control_rows[row]
            row_frame.grid(row=row,column=0,sticky='w')
            widget.grid(in_=row_frame,row=0,column=column,sticky='nw',padx=(0,12),pady=3)
            widget.lift()
            used+=needed;column+=1
        for frame in self._control_rows[row+1:]:frame.grid_remove()
        for widget,_key in self._texts:
            if isinstance(widget,ttk.Label):
                bound=max(100,width//2-12)if widget in self._note_labels and vertical else width
                if widget is self._intro_label and vertical:
                    bound=max(120,width-self._heading.winfo_reqwidth()-self._language_box.winfo_reqwidth()-24)
                if widget.cget('wraplength'):widget.configure(wraplength=bound)
                widget._vertical_max_width=bound
                widget.refresh_vertical()
        self._status_label.configure(wraplength=width)
        self._status_label._vertical_max_width=width
        self._status_label.refresh_vertical()
        self._canvas.configure(scrollregion=self._canvas.bbox('all'))

    def _scroll_content(self,event):
        widget=event.widget
        while widget is not None:
            if widget is self.table:return
            widget=getattr(widget,'master',None)
        self._canvas.yview_scroll(-int(event.delta/120),'units')
        return 'break'

    def _load_saved(self):
        try:
            current=[item.strip() for item in self.peers.get().split(',') if item.strip()]
            self.monitor.peers=normalize_peers(current,allow_internet=self.internet.get(),allow_lan=self.lan.get())
            self.monitor.load_saved()
            self.peers.set(', '.join(self.monitor.peers))
            self.internet.set(self.monitor.allow_internet);self.lan.set(self.monitor.allow_lan)
            self.status.set(str(tr(self.monitor.load_error or 'Saved SMW peer addresses loaded')))
        except Exception:
            self.status.set(str(tr('Some saved node addresses could not be loaded')))

    def _open_smw(self):
        if self._sumuww_process is not None and self._sumuww_process.poll() is None:return
        try:
            if getattr(sys,'frozen',False):
                executable=Path(sys.executable).with_name('SUMUWW.exe')
                if not executable.is_file():raise OSError('SMW executable missing')
                command=[str(executable)];directory=executable.parent
            else:
                command=[sys.executable,'-m','sumuww.app'];directory=Path(__file__).resolve().parent.parent
            self._sumuww_process=subprocess.Popen(command,cwd=directory,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            self.open_button.configure(state='disabled')
        except OSError:
            messagebox.showerror(str(tr('SMW Node Monitor')),str(tr('SMW could not be opened')),parent=self.root)

    def _check(self):
        try:
            self.monitor.results=[]
            for item in self.table.get_children():self.table.delete(item)
            peers=[item.strip() for item in self.peers.get().split(',') if item.strip()]
            if not peers:
                self.status.set(str(tr('No known nodes. Add a node address to check.')))
                self._finish_check()
                return
            self.monitor.configure(peers,allow_internet=self.internet.get(),allow_lan=self.lan.get())
            self._future=self.monitor.check()
            self.check_button.configure(state='disabled')
            self.peer_entry.configure(state='disabled')
            self.load_button.configure(state='disabled')
            for control in self._control_widgets[:2]:control.configure(state='disabled')
            self.status.set(str(tr('Checking known nodes...')))
        except Exception as error:
            messagebox.showerror(str(tr('SMW Node Monitor')),str(error),parent=self.root)

    def _show_results(self):
        for item in self.table.get_children():self.table.delete(item)
        names={'reachable':'Reachable SMW node','unreachable':'Unreachable','wrong_network':'Wrong network','protocol_error':'Invalid protocol'}
        groups={}
        for result in self.monitor.results:
            key=('node',result['peer_id']) if result['status']=='reachable' and result.get('peer_id') else ('address',result['endpoint'])
            groups.setdefault(key,[]).append(result)
        for group in groups.values():
            result=group[-1]
            addresses=', '.join(item['endpoint'] for item in group)
            tip=result['advertised_tip'] or '—'
            latency=', '.join('—' if item['latency_ms'] is None else str(item['latency_ms'])+' ms' for item in group)
            self.table.insert('', 'end',values=(addresses,result.get('peer_id') or '—',str(tr(names[result['status']])),tip,latency,str(tr(result['reason']))))
        total=len(self.monitor.results)
        reached=sum(item['status']=='reachable' for item in self.monitor.results)
        distinct=len({item.get('peer_id') or item['endpoint'] for item in self.monitor.results if item['status']=='reachable'})
        if self.monitor.results:self.status.set(str(tr('Responding addresses: {0} | Distinct nodes: {1} | No valid response: {2} | Checked addresses: {3}',reached,distinct,total-reached,total)))

    def _finish_check(self):
        if self._result_file is not None and not self._reported:
            self._result_file.parent.mkdir(parents=True,exist_ok=True)
            report={'application_version':__version__,'network':self.monitor.network,
                    'results':self.monitor.results,'scope':'On-demand P2P identity checks of known contacts only; no full chain validation or worldwide census',
                    'wallet_chain_or_rpc_credentials_opened':False,'node_hosted_or_restarted':False}
            with self._result_file.open('x',encoding='utf-8') as output:
                json.dump(report,output,ensure_ascii=False,indent=2);output.write('\n')
            self._reported=True
        if self._close_after_check:self._close()

    def _tick(self):
        self._tick_job=None
        if self._destroyed:return
        if self._future is not None and self._future.done():
            try:
                self.monitor.results=self._future.result()
                if not self._closing:
                    self._show_results()
                    self.peers.set(', '.join(self.monitor.peers))
                    self._finish_check()
            except Exception:
                self.status.set(str(tr('Node check failed')))
            self._future=None
            self.check_button.configure(state='normal');self.peer_entry.configure(state='normal');self.load_button.configure(state='normal')
            for control in self._control_widgets[:2]:control.configure(state='normal')
        if self._sumuww_process is not None and self._sumuww_process.poll() is not None:
            self._sumuww_process=None;self.open_button.configure(state='normal')
        if self._closing and self._future is None:
            self.root.destroy();return
        self._tick_job=self.root.after(100,self._tick)

    def _close(self):
        self._closing=True
        self.monitor.close()

    def _change_language(self,_event=None):
        code=next(code for code,name in LANGUAGES if name==self.language.get())
        self._translator.set_language(code)
        save_language(code,self._language_path)
        self._apply_language()

    def _apply_language(self):
        from .brand import apply_window_icon
        apply_window_icon(self.root, self._translator.language)
        vertical=self._translator.language=='mn-Mong'
        self.root.title(str(tr('SUMUWW'))if vertical else str(tr('SMW Node Monitor')))
        family={'ko':'Malgun Gothic','zh':'Microsoft YaHei','hi':'Nirmala UI','ar':'Tahoma',
                'ur':'Arial','bn':'Nirmala UI','ta':'Nirmala UI','th':'Leelawadee UI',
                'ja':'Yu Gothic UI','zh-TW':'Microsoft JhengHei','zh-HK':'Microsoft JhengHei'}.get(self._translator.language,'Segoe UI')
        ttk.Style(self.root).configure('.',font=(family,13 if self._translator.language=='ar' else 10))
        ttk.Style(self.root).configure('Treeview',rowheight=32 if self._translator.language=='ar' else 23)
        for widget,key in self._texts:widget.configure(text=str(tr(key)))
        self._heading.grid(row=0,column=0,sticky='nw'if vertical else'w')
        self._language_box.grid(row=0,column=2,sticky='ne'if vertical else'e')
        self._intro_label.grid(row=0 if vertical else 1,column=1 if vertical else 0,
                              columnspan=1 if vertical else 3,sticky='nw'if vertical else'ew',
                              padx=12 if vertical else 0,pady=0 if vertical else(10,0))
        for key,label in zip(('endpoint','peer_id','status','tip','latency','reason'),('Node address','Node ID','Status','Advertised tip','Latency','Result details')):
            self.table.heading(key,text=str(tr(label)))
        self._peer_caption.grid(row=0,column=0,columnspan=1 if vertical else 2,sticky='w',padx=(0,12)if vertical else 0)
        self.peer_entry.grid(row=0 if vertical else 1,column=1 if vertical else 0,
                             columnspan=1 if vertical else 2,sticky='ew',pady=5)
        self.table.configure(height=3 if vertical else 8)
        for index,widget in enumerate(self._note_labels):
            widget.grid(row=0 if vertical else index,column=index if vertical else 0,
                        columnspan=1 if vertical else 2,sticky='nw'if vertical else'ew',
                        padx=(0,12)if vertical else 0,pady=(0,6))
            self._notes.columnconfigure(index,weight=1)
        if self.monitor.results:self._show_results()
        else:self.status.set(str(tr('Checking known nodes...' if self._future is not None else 'Ready for an on-demand check')))
        self._canvas.yview_moveto(0)
        self._schedule_reflow()


def main(argv=None):
    parser=argparse.ArgumentParser(description='SMW read-only on-demand node monitor')
    parser.add_argument('--directory',type=Path,default=None)
    parser.add_argument('--network',choices=NETWORK_NAMES,default='dora')
    parser.add_argument('--peer',action='append',default=None)
    parser.add_argument('--allow-internet',action='store_true')
    parser.add_argument('--allow-lan',action='store_true')
    parser.add_argument('--check',action='store_true',help='Explicitly check the supplied known nodes when the screen opens')
    parser.add_argument('--node-directory',type=Path,default=None,help='Read public contact JSON only from this existing SMW data folder')
    parser.add_argument('--result-file',type=Path,default=None,help='Explicitly save query results to a new file; never overwrites existing files')
    parser.add_argument('--close-after-check',action='store_true',help='Close only the monitor window after the explicitly requested check')
    options=parser.parse_args(argv)
    try:
        saved_directory=options.node_directory or (default_directory() if options.directory is None else None)
    except (OSError,ValueError,TypeError):saved_directory=None
    if not options.check and options.peer is None:
        from .network_monitor_ui import NetworkMonitorApp
        root=tk.Tk()
        app=NetworkMonitorApp(root,options.directory or monitor_directory(),network=options.network)
        root.mainloop()
        return 0
    monitor=NodeMonitor(options.directory or monitor_directory(),network=options.network,peers=options.peer,
                        allow_internet=options.allow_internet,allow_lan=options.allow_lan,saved_node_directory=saved_directory)
    root=tk.Tk();app=NodeManagerApp(root,monitor,result_file=options.result_file,close_after_check=options.close_after_check)
    if options.check:root.after(0,app._check)
    try:root.mainloop()
    finally:monitor.close()
    return 0


if __name__=='__main__':
    raise SystemExit(main())
