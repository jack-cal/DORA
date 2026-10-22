# SUMUWW Android user guide

## Wallet and installation

Install or update using the signed APK. Keep an encrypted wallet backup and recovery words before updating or changing devices. Open an existing wallet, create one or restore it through Wallet management. Never share wallet passwords, private keys or recovery words.

The phone operates its own node and wallet. A PC wallet is not required. Connect to a compatible peer and complete synchronization before main-network mining.

## Main screens and transfers

Home, Mining, Wallet and More display the current node and wallet status. Send shows the recipient, amount, fee and total debit before signing. Receive provides the wallet address for copying or sharing. History distinguishes pending and confirmed transactions. A transfer is confirmed only after inclusion in the active chain; its confirmation count can change after a chain reorganization.

Newly issued mining rewards require a spending block height at least 100 greater than their creation height. An ordinary transfer of a mature reward does not impose another 100-block maturity period on the recipient.

## Mining and protection

Start and Stop control the current mining batch. Total elapsed time includes preparation and waiting. Search duration measures wall time inside nonce search, including operating-system scheduling delays. H/s reports attempted hashes and does not predict when a reward will be found. Network waiting accumulates across the batch.

Android scheduling and power management can reduce background speed or interrupt operation. The battery floor defaults to 15 percent, and mining stops at or below the configured floor. Battery and thermal protections also stop mining when their conditions are met. Restarting after a protection stop is manual. Allowing background operation does not guarantee the same speed as foreground operation.

## Language and appearance

Settings provide 34 languages, light/dark appearance, colors and seasonal themes. Traditional Mongolian uses vertical text. Node connections, mining controls, backup, recovery and help are available in the app settings.

## Permissions and consent

Review before using SUMUWW. Required agreements must be accepted before the node starts. Mining starts only when you press Start.

[Required] Device mining and background operation: CPU, battery and mobile data are used. Heat and reduced performance are possible. Mining and node traffic can continue while another app is open or the screen is off. Stop from SUMUWW or its notification.

[Required] Peer communication: blocks and transactions are exchanged over the Internet. Peers can see your connection IP. Addresses and confirmed transactions are public on the blockchain; never disclose your password or recovery words.

Withdrawing required consent stops the node and mining and returns to the consent screen. Wallet and chain files are preserved.

## IP protection

Tor and I2P are optional and bundled with SUMUWW. Only the selected router runs; Direct runs neither. No separate router installation or port setting is needed. If a private connection fails, it does not switch to Direct. I2P requires b32.i2p peers.

Local router port: Tor SOCKS5 `127.0.0.1:9050`; I2P SAM `127.0.0.1:7656`.
