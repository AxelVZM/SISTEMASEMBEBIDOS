#pragma once
#include <algorithm>
#include <cassert>
#include <cstdint>
#include <cstring>
#include <iomanip>
#include <map>
#include <memory>
#include <sstream>
#include <string>
#include <type_traits>
#include <vector>
struct String {
 std::string value;
 String()=default;String(const char *s):value(s?s:""){}String(const std::string&s):value(s){}String(char c):value(1,c){}
 template<class T,typename=std::enable_if_t<std::is_integral_v<T>>>String(T n):value(std::to_string(n)){}
 String(float n,int p=2){std::ostringstream s;s<<std::fixed<<std::setprecision(p)<<n;value=s.str();}
 size_t length()const{return value.size();}const char*c_str()const{return value.c_str();}char operator[](size_t i)const{return value[i];}
 void reserve(size_t n){value.reserve(n);}String substring(size_t a,size_t b=std::string::npos)const{return value.substr(a,b==std::string::npos?b:b-a);}
 void remove(size_t start,size_t count=std::string::npos){value.erase(start,count);}
 void replace(const char*from,const char*to){size_t p=0;while((p=value.find(from,p))!=std::string::npos){value.replace(p,strlen(from),to);p+=strlen(to);}}
 String&operator+=(const String&s){value+=s.value;return *this;}friend String operator+(String a,const String&b){a+=b;return a;}
};
struct Preferences {
 std::map<std::string,std::vector<uint8_t>>values;bool fail=false;
 bool begin(const char*,bool){return true;}size_t getBytesLength(const char*k){return values.count(k)?values[k].size():0;}
 size_t getBytes(const char*k,void*p,size_t n){size_t c=std::min(n,getBytesLength(k));if(c)memcpy(p,values[k].data(),c);return c;}
 size_t putBytes(const char*k,const void*p,size_t n){if(fail)return 0;auto*b=static_cast<const uint8_t*>(p);values[k]=std::vector<uint8_t>(b,b+n);return n;}
 bool getBool(const char*k,bool d){return values.count(k)?values[k][0]!=0:d;}size_t putBool(const char*k,bool v){uint8_t b=v;return putBytes(k,&b,1);}
 bool remove(const char*k){return !fail&&values.erase(k)>0;}
};
struct File {std::shared_ptr<std::string>data;size_t pos=0;bool writable=false;bool*fail=nullptr;
 explicit operator bool()const{return bool(data);}size_t size()const{return data?data->size():0;}void close(){data.reset();}void flush(){}
 size_t position()const{return pos;}
 size_t print(const String&s){if(!data||!writable||(fail&&*fail))return 0;data->append(s.value);pos=data->size();return s.length();}
 size_t read(uint8_t*p,size_t n){if(!data)return 0;n=std::min(n,data->size()-pos);memcpy(p,data->data()+pos,n);pos+=n;return n;}
};
struct FakeFS {std::map<std::string,std::shared_ptr<std::string>>files;bool mounted=false,failWrite=false;int formats=0;
 bool begin(bool){return mounted;}bool format(){formats++;files.clear();mounted=true;return true;}
 bool exists(const char*p){return files.count(p);}bool remove(const char*p){return files.erase(p)>0;}
 bool rename(const char*a,const char*b){if(!files.count(a))return false;files[b]=files[a];files.erase(a);return true;}
 File open(const char*p,const char*mode){bool write=mode[0]=='a';if(!mounted||(!write&&!files.count(p)))return {};if(write&&!files.count(p))files[p]=std::make_shared<std::string>();File f;f.data=files[p];f.writable=write;f.pos=write?f.data->size():0;f.fail=&failWrite;return f;}
}LittleFS;
