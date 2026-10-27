#pragma once
#include <cstring>
namespace detector {
struct KnownModel {const char*code;const char*brand;const char*name;};
inline const KnownModel* knownModel(const char*code){
 // Exact advertised codes only. Sources in BASE_TECNICA_7_5.md.
 static const KnownModel models[]={{"SM-S911B","Samsung","Galaxy S23"},{"SM-S911B/DS","Samsung","Galaxy S23"},{"BVL-N49","Honor","Magic6 Pro"},{"FNE-NX9","Honor","HONOR 70"}};
 for(auto&m:models)if(!strcmp(code,m.code))return &m;return nullptr;
}
// Normalize only an explicitly announced manufacturer, never SSID/OUI/chip vendor.
inline const char* canonicalBrand(const char*s){
 if(!s||!*s)return "";
 struct Alias {const char*key;const char*brand;};
 static const Alias aliases[]={{"samsung","Samsung"},{"honor","Honor"},{"apple","Apple"},{"xiaomi","Xiaomi"},{"huawei","Huawei"},{"lenovo","Lenovo"},{"motorola","Motorola"},{"google","Google"},{"sony","Sony"},{"epson","Epson"},{"canon","Canon"},{"brother","Brother"},{"hewlett-packard","HP"},{"hp","HP"},{"asus","ASUS"},{"dell","Dell"},{"acer","Acer"},{"tp-link","TP-Link"},{"tplink","TP-Link"},{"hikvision","Hikvision"},{"dahua","Dahua"},{"lg","LG"},{"oppo","OPPO"},{"vivo","vivo"},{"realme","realme"},{"oneplus","OnePlus"}};
 while(*s==' ')s++;
 for(auto&a:aliases){size_t i=0;for(;a.key[i]&&s[i];i++){char c=s[i];if(c>='A'&&c<='Z')c+=32;if(c!=a.key[i])break;}
  if(!a.key[i]&&(!s[i]||s[i]==' '||s[i]==','||s[i]=='.'))return a.brand;
 }
 return s;
}
inline const KnownModel* compatibleModel(const char*brand,const char*code){auto*m=knownModel(code);return m&&(!*brand||!strcmp(canonicalBrand(brand),m->brand))?m:nullptr;}
}
