// SPDX-License-Identifier: MIT
#define _GNU_SOURCE
#include <assert.h>
#include <dlfcn.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
int main(int argc,char**argv){
 assert(argc==2);void *lib=dlopen(argv[1],RTLD_NOW|RTLD_LOCAL);
 if(!lib){puts(dlerror());return 1;}
 int(*answer)(int)=dlsym(lib,"purifier_answer");assert(answer);
 assert(answer(0)==42 && answer(1)==43);
 Dl_info info;assert(dladdr(answer,&info));
 char *actual=realpath(info.dli_fname,NULL),*expected=realpath(argv[1],NULL);
 assert(actual && expected && strcmp(actual,expected)==0);
 free(actual);free(expected);assert(dlclose(lib)==0);
 puts("C bind(C)42/43 +origin +scoped close passed");
}
