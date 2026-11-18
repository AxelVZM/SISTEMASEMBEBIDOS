#include "wifi_header.h"
#include <string.h>
bool wifi_identity(const uint8_t *p,size_t len,wifi_identity_t *out) {
    if(len<24 || (p[0]&3)!=0) return false;
    unsigned type=(p[0]>>2)&3, sub=p[0]>>4, ds=p[1]&3;
    if(type!=0 && type!=2) return false;
    const uint8_t *tx=p+10; // Transmitter only; no receiver or payload extraction.
    if(tx[0]&1) return false;
    bool zero=true; for(int i=0;i<6;i++) if(tx[i]) zero=false;
    if(zero) return false;
    memcpy(out->mac,tx,6); out->role=0;
    out->frame=type==2?"data":"management";
    if(type==0 && (sub==8 || sub==5)) {out->role=1;out->frame=sub==8?"beacon":"probe_response";}
    else if(type==0 && sub==4) {out->role=2;out->frame="probe_request";}
    else if(type==2 && ds==1) out->role=2;
    else if(type==2 && ds==2) out->role=1;
    // WDS/mesh and other management roles remain unknown.
    return true;
}
