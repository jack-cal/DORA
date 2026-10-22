package org.sumuww.miner
import java.io.InputStream
import java.io.ByteArrayOutputStream

/** Bounded encrypted-envelope transport only; PC keystore validates its contents. */
internal object WalletBackupIo {
 fun read(input:InputStream):ByteArray {
  val output=ByteArrayOutputStream();val buffer=ByteArray(1024);var emptyReads=0
  while(true){
   val count=input.read(buffer)
   if(count<0)break
   if(count==0){emptyReads++;check(emptyReads<4){"Backup provider returned no data"};continue}
   emptyReads=0
   require(output.size()+count<=4096){"Encrypted wallet exceeds4096bytes"}
   output.write(buffer,0,count)
  }
  require(output.size()>0){"Encrypted wallet is empty"}
  return output.toByteArray()
 }
}
