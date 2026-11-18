#include <assert.h>
#include <string.h>
#include "wifi_header.h"
#include "recovery_policy.h"
int main(void){
 assert(detector_recovery_allowed(0,0));assert(detector_recovery_allowed(2,2));
 assert(!detector_recovery_allowed(3,0));assert(!detector_recovery_allowed(0,3));assert(!detector_recovery_allowed(100,100));
 uint8_t p[40]={0};wifi_identity_t out;p[0]=0x80;p[10]=0x04;p[11]=0xb2;p[12]=0x47;p[13]=0x97;p[14]=0xd9;p[15]=0x8c;
 assert(!wifi_identity(p,23,&out));assert(wifi_identity(p,24,&out));assert(out.role==1);assert(strcmp(out.frame,"beacon")==0);
 p[0]=0x40;assert(wifi_identity(p,24,&out)&&out.role==2);
 p[0]=0x08;p[1]=1;assert(wifi_identity(p,24,&out)&&out.role==2);
 p[1]=2;assert(wifi_identity(p,24,&out)&&out.role==1);
 p[1]=3;assert(wifi_identity(p,30,&out)&&out.role==0);
 p[10]=1;assert(!wifi_identity(p,24,&out));p[0]=0xd4;assert(!wifi_identity(p,24,&out));
 return 0;
}
