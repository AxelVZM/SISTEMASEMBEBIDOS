#pragma once
#include "lan_core.h"
#include <cstdio>
namespace detector {
struct LocalDescription {uint8_t ip[4]{};uint16_t port=80;char path[257]{};};
inline bool localDescriptionUrl(const char*s,const uint8_t*peer,const uint8_t*local,const uint8_t*mask,LocalDescription&out){
 if(strncmp(s,"http://",7))return false;s+=7;unsigned a,b,c,d,port=80;int used=0;
 if(sscanf(s,"%u.%u.%u.%u%n",&a,&b,&c,&d,&used)!=4||a>255||b>255||c>255||d>255)return false;
 uint8_t ip[4]={uint8_t(a),uint8_t(b),uint8_t(c),uint8_t(d)};
 if(!a||a==127||a>=224||!memcmp(ip,local,4)||memcmp(ip,peer,4))return false;
 bool hostZero=true,hostOnes=true;for(int i=0;i<4;i++){if((ip[i]&mask[i])!=(local[i]&mask[i]))return false;if(ip[i]&~mask[i])hostZero=false;if((ip[i]|mask[i])!=255)hostOnes=false;}
 if(hostZero||hostOnes)return false;s+=used;
 if(*s==':'){s++;if(*s<'0'||*s>'9')return false;port=0;while(*s>='0'&&*s<='9'){port=port*10+(*s++-'0');if(port>65535)return false;}if(!port)return false;}
 if(*s!='/'||strlen(s)>256)return false;
 for(const char*p=s;*p;p++)if(uint8_t(*p)<=32||uint8_t(*p)>=127||*p=='#'||*p=='\\')return false;
 memcpy(out.ip,ip,4);out.port=port;strcpy(out.path,s);return true;
}
inline bool ssdpLocation(const char*packet,char*out,size_t cap){
 if(strncmp(packet,"HTTP/1.1 200 ",13))return false;bool found=false;
 const char*p=strstr(packet,"\r\n");if(!p)return false;p+=2;
 while(*p){const char*end=strstr(p,"\r\n");if(!end)return false;if(end==p)return found;
  const char*colon=(const char*)memchr(p,':',end-p);if(!colon)return false;
  if(colon-p==8){const char*key="location";size_t k=0;while(k<8&&lowerAscii(p[k])==key[k])k++;
   if(k==8){if(found)return false;const char*v=colon+1;while(v<end&&(*v==' '||*v=='\t'))v++;while(end>v&&(end[-1]==' '||end[-1]=='\t'))end--;size_t n=end-v;if(!n||n>=cap)return false;memcpy(out,v,n);out[n]=0;found=true;}
  }
  p=strstr(p,"\r\n")+2;
 }
 return false;
}
inline bool xmlText(const char*p,size_t n,char*out,size_t cap){
 char buf[193];size_t j=0;for(size_t i=0;i<n;i++){
  char c=p[i];if(c=='&'){struct Entity{const char*s;char c;};static const Entity es[]={{"&amp;",'&'},{"&lt;",'<'},{"&gt;",'>'},{"&quot;",'"'},{"&apos;",'\''}};bool ok=false;for(auto&e:es){size_t m=strlen(e.s);if(i+m<=n&&!memcmp(p+i,e.s,m)){c=e.c;i+=m-1;ok=true;break;}}if(!ok)return false;}
  if((uint8_t(c)<32&&c!='\t'&&c!='\n'&&c!='\r')||j>=sizeof(buf)-1)return false;buf[j++]=c;
 }
 size_t first=0;while(first<j&&uint8_t(buf[first])<=32)first++;while(j>first&&uint8_t(buf[j-1])<=32)j--;
 if(j-first>=cap)return false;return j==first?true:copyUtf8(out,cap,(const uint8_t*)buf+first,j-first);
}
// Deliberately small XML subset: no DTD/entities expansion, max depth 16,
// root device fields only. Unsupported encodings/markup remain unidentified.
inline bool upnpDescription(const char*xml,LanEntry&out){
 if(!xml||strlen(xml)>8192)return false;
 LanEntry e=out;char tags[16][48]{};unsigned depth=0;bool root=false,done=false,device=false;const char*p=xml;
 while(*p){
  if(*p!='<'){const char*end=strchr(p,'<');if(!end){while(*p&&uint8_t(*p)<=32)p++;if(!*p&&done)break;return false;}
   if(depth==3&&!strcmp(tags[0],"root")&&!strcmp(tags[1],"device")){
    char*dst=nullptr;size_t cap=0;const char*k=tags[2];
    if(!strcmp(k,"manufacturer")){dst=e.brand;cap=sizeof(e.brand);}else if(!strcmp(k,"modelName")){dst=e.model;cap=sizeof(e.model);}else if(!strcmp(k,"modelNumber")){dst=e.modelCode;cap=sizeof(e.modelCode);}else if(!strcmp(k,"friendlyName")){dst=e.name;cap=sizeof(e.name);}else if(!strcmp(k,"deviceType")){dst=e.upnpType;cap=sizeof(e.upnpType);}
    if(dst){if(*dst)return false;if(!xmlText(p,end-p,dst,cap))return false;}
   }else if(!depth){for(auto*q=p;q<end;q++)if(uint8_t(*q)>32)return false;}
   p=end;continue;
  }
  if(!strncmp(p,"<!--",4)){const char*end=strstr(p+4,"-->");if(!end)return false;p=end+3;continue;}
  if(!strncmp(p,"<?xml ",6)&&!root){const char*end=strstr(p,"?>");if(!end)return false;p=end+2;continue;}
  if(p[1]=='!'||p[1]=='?')return false;
  bool close=p[1]=='/';p+=close?2:1;char tag[48]{};size_t n=0;
  while(*p&&*p!='>'&&*p!='/'&&uint8_t(*p)>32){if(n>=sizeof(tag)-1)return false;tag[n++]=*p++;}if(!n)return false;
  // Namespaces on root accepted as attributes; prefixed element names unsupported.
  char quoteChar=0;while(*p&&(*p!='>'||quoteChar)){if(*p=='\''||*p=='"'){if(!quoteChar)quoteChar=*p;else if(quoteChar==*p)quoteChar=0;}p++;}if(!*p)return false;
  bool self=p[-1]=='/';p++;
  if(close){if(!depth||strcmp(tags[depth-1],tag))return false;if(--depth==0)done=true;}
  else {if(done||depth>=16)return false;if(!depth){if(root||strcmp(tag,"root"))return false;root=true;}if(depth==1&&!strcmp(tag,"device")){if(device)return false;device=true;}strcpy(tags[depth++],tag);if(self)depth--;}
 }
 if(!root||!done||depth||!device||!e.upnpType[0])return false;
 char brand[65]{};const char*b=canonicalBrand(e.brand);copyUtf8(brand,sizeof(brand),(const uint8_t*)b,strlen(b));memcpy(e.brand,brand,sizeof(brand));strcpy(e.evidence,"UPnP XML; datos declarados");out=e;return true;
}
}
