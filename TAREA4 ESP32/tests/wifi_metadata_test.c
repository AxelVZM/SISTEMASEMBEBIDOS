#include <assert.h>
#include <string.h>
#include <stdint.h>
#include "wifi_metadata.h"
static size_t field(uint8_t *p,unsigned tag,const uint8_t *v,size_t n){p[0]=tag>>8;p[1]=tag;p[2]=n>>8;p[3]=n;memcpy(p+4,v,n);return n+4;}
int main(void){
 uint8_t f[1100]={0},attributes[384]={0};size_t n=0;wifi_metadata_t out;
 f[0]=0x80;
 n+=field(attributes+n,0x1021,(const uint8_t*)"ZTE",3);
 n+=field(attributes+n,0x1023,(const uint8_t*)"ZXHN F680",9);
 n+=field(attributes+n,0x1024,(const uint8_t*)"F680",4);
 n+=field(attributes+n,0x1011,(const uint8_t*)"EPSON_Projector",15);
 const uint8_t type[]={0,6,0,0x50,0xf2,4,0,2};n+=field(attributes+n,0x1054,type,8);
 /* Two WPS IEs with a TLV deliberately split between them, followed by SSID IE 0. */
 size_t split=6,at=36;f[at++]=221;f[at++]=split+4;memcpy(f+at,"\x00\x50\xf2\x04",4);at+=4;memcpy(f+at,attributes,split);at+=split;
 f[at++]=221;f[at++]=n-split+4;memcpy(f+at,"\x00\x50\xf2\x04",4);at+=4;memcpy(f+at,attributes+split,n-split);at+=n-split;
 f[at++]=0;f[at++]=9;memcpy(f+at,"ZTE_F680A",9);at+=9;
 wifi_metadata(f,at,&out);
 assert(strcmp(out.device_name,"EPSON_Projector")==0);
 assert(strcmp(out.ssid,"ZTE_F680A")==0);
 assert(strcmp(out.manufacturer,"ZTE")==0);
 assert(strcmp(out.model_name,"ZXHN F680")==0);
 assert(strcmp(out.primary_device_type,"00060050F2040002")==0);
 wifi_metadata(f,20,&out);assert(!out.manufacturer[0]);assert(!out.ssid[0]);
 wifi_metadata(f,at-1,&out);assert(!out.manufacturer[0]);assert(!out.ssid[0]);
 f[0]=8;wifi_metadata(f,at,&out);assert(!out.manufacturer[0]);
 f[0]=0x80;f[36]=1;wifi_metadata(f,at,&out);assert(!out.manufacturer[0]);
 /* Malformed TLV lengths and arbitrary input must never read outside a record. */
 uint32_t seed=1;
 for(unsigned i=0;i<10000;i++){size_t length=i%sizeof(f);for(size_t j=0;j<length;j++){seed=seed*1664525U+1013904223U;f[j]=seed>>24;}wifi_metadata(f,length,&out);assert(out.manufacturer[64]==0);assert(out.device_name[32]==0);assert(out.ssid[32]==0);}
 /* Android Wi-Fi Direct probe request: P2P Device Info carries phone type and name; Samsung/Broadcom vendor IEs. */
 memset(f,0,sizeof(f));f[0]=0x40;at=24;
 f[at++]=0;f[at++]=7;memcpy(f+at,"DIRECT-",7);at+=7;
 f[at++]=221;f[at++]=5;memcpy(f+at,"\x00\x00\xf0\x22\x01",5);at+=5;
 f[at++]=221;f[at++]=5;memcpy(f+at,"\x00\x10\x18\x02\x00",5);at+=5;
 uint8_t info[64];size_t k=0;memset(info,0,sizeof(info));
 k+=6;info[k++]=0x01;info[k++]=0x88;
 memcpy(info+k,"\x00\x0a\x00\x50\xf2\x04\x00\x05",8);k+=8;info[k++]=0;
 info[k++]=0x10;info[k++]=0x11;info[k++]=0;info[k++]=10;memcpy(info+k,"Galaxy A54",10);k+=10;
 f[at++]=221;f[at++]=4+3+k;memcpy(f+at,"\x50\x6f\x9a\x09",4);at+=4;f[at++]=13;f[at++]=k&0xff;f[at++]=k>>8;memcpy(f+at,info,k);at+=k;
 wifi_metadata(f,at,&out);
 assert(strcmp(out.device_name,"Galaxy A54")==0);
 assert(strcmp(out.primary_device_type,"000A0050F2040005")==0);
 assert(strstr(out.vendor_ies,"0000F022"));assert(strstr(out.vendor_ies,"506F9A09"));assert(!out.ssid[0]);
 return 0;
}
