#include "wifi_metadata.h"
#include <string.h>
#include <stdio.h>
static unsigned be16(const uint8_t *p){return ((unsigned)p[0]<<8)|p[1];}
static void copy_text(char *out,size_t capacity,const uint8_t *data,size_t length){
    size_t n=length<capacity-1?length:capacity-1;
    for(size_t i=0;i<n;i++)out[i]=(data[i]>=32 && data[i]<127)?(char)data[i]:'?';
    out[n]=0;
}
static void hex_type(char *out,const uint8_t *value){for(unsigned i=0;i<8;i++)snprintf(out+i*2,3,"%02X",value[i]);}
static void add_vendor(wifi_metadata_t *out,unsigned *count,const uint8_t *data,unsigned n){
    if(*count>=8 || n<3)return;
    char tag[10];
    if(n>=4)snprintf(tag,sizeof(tag),"%02X%02X%02X%02X",data[0],data[1],data[2],data[3]);
    else snprintf(tag,sizeof(tag),"%02X%02X%02X",data[0],data[1],data[2]);
    if(strstr(out->vendor_ies,tag))return;
    size_t used=strlen(out->vendor_ies);
    if(used+strlen(tag)+2>sizeof(out->vendor_ies))return;
    if(used)out->vendor_ies[used++]=',';
    strcpy(out->vendor_ies+used,tag);(*count)++;
}
void wifi_metadata(const uint8_t *frame,size_t length,wifi_metadata_t *out){
    memset(out,0,sizeof(*out));
    if(length<24 || (frame[0]&0x0f)!=0)return;
    unsigned subtype=frame[0]>>4;size_t offset;
    if(subtype==8 || subtype==5)offset=36;      /* beacon / probe response */
    else if(subtype==4)offset=24;               /* probe request */
    else if(subtype==0)offset=28;               /* association request */
    else if(subtype==2)offset=34;               /* reassociation request */
    else return;
    if(length<offset)return;
    uint8_t attributes[384];size_t used=0;
    uint8_t p2p[256];size_t p2p_used=0;
    unsigned vendors=0;
    const uint8_t *ssid_ptr=NULL;size_t ssid_len=0;
    size_t end=length<offset+1024?length:offset+1024;
    for(size_t at=offset;at+2<=end;){
        unsigned id=frame[at],n=frame[at+1];at+=2;
        if(n>end-at){memset(out,0,sizeof(*out));return;}
        const uint8_t *data=frame+at;
        if(id==0 && (subtype==8 || subtype==5) && n>=1 && n<=32 && data[0]!=0){
            ssid_ptr=data;ssid_len=n;
        }else if(id==221 && n>=4 && memcmp(data,"\x00\x50\xf2\x04",4)==0){
            if(n-4>sizeof(attributes)-used){memset(out,0,sizeof(*out));return;}
            memcpy(attributes+used,data+4,n-4);used+=n-4;
        }else if(id==221 && n>=4 && memcmp(data,"\x50\x6f\x9a\x09",4)==0){
            /* Wi-Fi Direct (P2P) IE: attributes may span several IEs. */
            add_vendor(out,&vendors,data,n);
            if(n-4<=sizeof(p2p)-p2p_used){memcpy(p2p+p2p_used,data+4,n-4);p2p_used+=n-4;}
        }else if(id==221 && n>=3){
            add_vendor(out,&vendors,data,n);
        }
        at+=n;
    }
    if(ssid_ptr)copy_text(out->ssid,sizeof(out->ssid),ssid_ptr,ssid_len);
    for(size_t at=0;at+4<=used;){
        unsigned tag=be16(attributes+at),n=be16(attributes+at+2);at+=4;
        if(n>used-at){char keep[72];memcpy(keep,out->vendor_ies,sizeof(keep));memset(out,0,sizeof(*out));memcpy(out->vendor_ies,keep,sizeof(keep));used=0;break;}
        const uint8_t *value=attributes+at;
        if(tag==0x1011)copy_text(out->device_name,sizeof(out->device_name),value,n);
        else if(tag==0x1021)copy_text(out->manufacturer,sizeof(out->manufacturer),value,n);
        else if(tag==0x1023)copy_text(out->model_name,sizeof(out->model_name),value,n);
        else if(tag==0x1024)copy_text(out->model_number,sizeof(out->model_number),value,n);
        else if(tag==0x1054 && n==8)hex_type(out->primary_device_type,value);
        at+=n;
    }
    /* P2P attributes: id(1) len(2, little endian) body. Device Info = 13. */
    for(size_t at=0;at+3<=p2p_used;){
        unsigned id=p2p[at],n=p2p[at+1]|((unsigned)p2p[at+2]<<8);at+=3;
        if(n>p2p_used-at)break;
        const uint8_t *v=p2p+at;
        if(id==13 && n>=17){
            /* addr(6) config(2) primary type(8) secondary count(1) secondary(8*k) name TLV */
            if(!out->primary_device_type[0])hex_type(out->primary_device_type,v+8);
            size_t pos=17+(size_t)v[16]*8;
            if(pos+4<=n && be16(v+pos)==0x1011){
                unsigned len=be16(v+pos+2);
                if(pos+4+len<=n && len && !out->device_name[0])copy_text(out->device_name,sizeof(out->device_name),v+pos+4,len);
            }
        }
        at+=n;
    }
}
