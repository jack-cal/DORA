"""OpenCL GPU SHA-256d search; every returned solution is checked on the CPU."""
import ctypes as C
import ctypes.util
import os
from dataclasses import replace
from .block import Block, MiningExhausted
from .primitives import valid_target, check_pow, require_int

KERNEL = r'''
__constant uint K[64]={
0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,
0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,
0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,
0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,
0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,
0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,
0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,
0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2};
uint rr(uint x,uint n){return (x>>n)|(x<<(32-n));}
uint swap(uint x){return ((x&255)<<24)|((x&65280)<<8)|((x>>8)&65280)|(x>>24);}
void init(uint *s){s[0]=0x6a09e667;s[1]=0xbb67ae85;s[2]=0x3c6ef372;s[3]=0xa54ff53a;s[4]=0x510e527f;s[5]=0x9b05688c;s[6]=0x1f83d9ab;s[7]=0x5be0cd19;}
void compress(uint *s,uint *w){
 for(uint i=16;i<64;i++){uint a=w[i-15],b=w[i-2];w[i]=w[i-16]+(rr(a,7)^rr(a,18)^(a>>3))+w[i-7]+(rr(b,17)^rr(b,19)^(b>>10));}
 uint a=s[0],b=s[1],c=s[2],d=s[3],e=s[4],f=s[5],g=s[6],h=s[7];
 for(uint i=0;i<64;i++){uint t=h+(rr(e,6)^rr(e,11)^rr(e,25))+((e&f)^(~e&g))+K[i]+w[i];uint u=(rr(a,2)^rr(a,13)^rr(a,22))+((a&b)^(a&c)^(b&c));h=g;g=f;f=e;e=d+t;d=c;c=b;b=a;a=t+u;}
 s[0]+=a;s[1]+=b;s[2]+=c;s[3]+=d;s[4]+=e;s[5]+=f;s[6]+=g;s[7]+=h;
}
__kernel void search(__global const uchar *header,__global const uint *target,uint start,__global uint *out){
 uint n=start+(uint)get_global_id(0),s[8],w[64];init(s);
 for(uint i=0;i<16;i++){uint k=4*i;w[i]=((uint)header[k]<<24)|((uint)header[k+1]<<16)|((uint)header[k+2]<<8)|header[k+3];}
 compress(s,w);
 for(uint i=0;i<16;i++)w[i]=0;
 for(uint i=0;i<3;i++){uint k=64+4*i;w[i]=((uint)header[k]<<24)|((uint)header[k+1]<<16)|((uint)header[k+2]<<8)|header[k+3];}
 w[3]=swap(n);w[4]=0x80000000;w[15]=640;compress(s,w);
 for(uint i=0;i<8;i++)w[i]=s[i];for(uint i=8;i<16;i++)w[i]=0;w[8]=0x80000000;w[15]=256;init(s);compress(s,w);
 int valid=1;for(int i=7;i>=0;i--){uint v=swap(s[i]);if(v<target[i])break;if(v>target[i]){valid=0;break;}}
 if(valid && atomic_cmpxchg(out,0u,1u)==0u)out[1]=n;
}
'''

class OpenCLMiner:
    mode = 'gpu'
    def __init__(self):
        library = 'OpenCL.dll' if os.name == 'nt' else (ctypes.util.find_library('OpenCL') or 'libOpenCL.so')
        try:
            self.lib = C.WinDLL(library) if os.name == 'nt' else C.CDLL(library)
        except OSError:
            raise ValueError('OpenCL GPU driver is not available') from None
        self.resources=[]
        v=C.c_void_p;u=C.c_uint;s=C.c_size_t;i=C.c_int;p=C.POINTER
        signatures={
          'clGetPlatformIDs':(i,[u,p(v),p(u)]),'clGetDeviceIDs':(i,[v,C.c_ulonglong,u,p(v),p(u)]),
          'clCreateContext':(v,[v,u,p(v),v,v,p(i)]),'clCreateCommandQueue':(v,[v,v,C.c_ulonglong,p(i)]),
          'clCreateProgramWithSource':(v,[v,u,p(C.c_char_p),p(s),p(i)]),'clBuildProgram':(i,[v,u,p(v),C.c_char_p,v,v]),
          'clCreateKernel':(v,[v,C.c_char_p,p(i)]),'clCreateBuffer':(v,[v,C.c_ulonglong,s,v,p(i)]),
          'clSetKernelArg':(i,[v,u,s,v]),'clEnqueueWriteBuffer':(i,[v,v,u,s,s,v,u,v,v]),
          'clEnqueueReadBuffer':(i,[v,v,u,s,s,v,u,v,v]),'clEnqueueNDRangeKernel':(i,[v,v,u,p(s),p(s),p(s),u,v,v]),
          'clFinish':(i,[v]),'clGetDeviceInfo':(i,[v,u,s,v,p(s)])}
        for name,(ret,args) in signatures.items():
            fn=getattr(self.lib,name);fn.restype=ret;fn.argtypes=args
        for name in ('MemObject','Kernel','Program','CommandQueue','Context'):
            fn=getattr(self.lib,'clRelease'+name);fn.restype=i;fn.argtypes=[v]
        try:
            count=u();self._ok(self.lib.clGetPlatformIDs(0,None,C.byref(count)))
            platforms=(v*count.value)();self._ok(self.lib.clGetPlatformIDs(count.value,platforms,None))
            device=None
            for platform in platforms:
                devices=(v*32)();n=u()
                if self.lib.clGetDeviceIDs(platform,4,32,devices,C.byref(n))==0 and n.value:
                    device=v(devices[0]);break
            if device is None:raise ValueError('No OpenCL GPU device found')
            self.device=device;error=i()
            self.context=self._resource('Context',self.lib.clCreateContext(None,1,C.byref(device),None,None,C.byref(error)),error)
            self.queue=self._resource('CommandQueue',self.lib.clCreateCommandQueue(self.context,device,0,C.byref(error)),error)
            src=C.c_char_p(KERNEL.encode());length=s(len(KERNEL.encode()))
            program=self._resource('Program',self.lib.clCreateProgramWithSource(self.context,1,C.byref(src),C.byref(length),C.byref(error)),error)
            self._ok(self.lib.clBuildProgram(program,1,C.byref(device),b'',None,None))
            self.kernel=self._resource('Kernel',self.lib.clCreateKernel(program,b'search',C.byref(error)),error)
            self.buffers=[self._resource('MemObject',self.lib.clCreateBuffer(self.context,1,size,None,C.byref(error)),error) for size in (80,32,8)]
            name=C.create_string_buffer(256);self._ok(self.lib.clGetDeviceInfo(device,0x102b,256,name,None));self.device_name=name.value.decode(errors='replace')
        except BaseException:
            self.close();raise
    def _ok(self,code):
        if code:raise ValueError(f'OpenCL operation failed ({code})')
    def _resource(self,kind,handle,error):
        self._ok(error.value)
        if not handle:raise ValueError('OpenCL allocation failed')
        self.resources.append((kind,handle));return handle
    def _write(self,buffer,data):
        self._ok(self.lib.clEnqueueWriteBuffer(self.queue,buffer,1,0,C.sizeof(data),C.byref(data),0,None,None))
    def search(self,header,pow_limit,cancel_check=None,max_attempts=1<<32):
        require_int(max_attempts,1,1<<32)
        raw=(C.c_ubyte*80).from_buffer_copy(header.serialize());target=valid_target(header.bits,pow_limit)
        words=(C.c_uint*8)(*[(target>>(32*i))&0xffffffff for i in range(8)])
        self._write(self.buffers[0],raw);self._write(self.buffers[1],words)
        for arg,buf in [(0,self.buffers[0]),(1,self.buffers[1]),(3,self.buffers[2])]:
            value=C.c_void_p(buf);self._ok(self.lib.clSetKernelArg(self.kernel,arg,C.sizeof(value),C.byref(value)))
        for start in range(0,max_attempts,32768):
            if cancel_check and cancel_check():raise RuntimeError('Mining cancelled')
            output=(C.c_uint*2)(0,0);self._write(self.buffers[2],output)
            value=C.c_uint(start);self._ok(self.lib.clSetKernelArg(self.kernel,2,4,C.byref(value)))
            size=C.c_size_t(min(32768,max_attempts-start))
            self._ok(self.lib.clEnqueueNDRangeKernel(self.queue,self.kernel,1,None,C.byref(size),None,0,None,None))
            self._ok(self.lib.clEnqueueReadBuffer(self.queue,self.buffers[2],1,0,8,C.byref(output),0,None,None))
            if output[0]:
                result=replace(header,nonce=output[1])
                if not check_pow(result.digest(),header.bits,pow_limit):raise ValueError('GPU returned invalid proof of work')
                return result
        raise MiningExhausted('GPU nonce space exhausted')
    def mine(self,block,pow_limit,cancel_check):
        return Block(self.search(block.header,pow_limit,cancel_check),block.transactions)
    def close(self):
        for kind,handle in reversed(getattr(self,'resources',[])):getattr(self.lib,'clRelease'+kind)(handle)
        self.resources=[]
