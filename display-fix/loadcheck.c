// Load and resolve the library only. Never call power-management functions.
#include <dlfcn.h>
#include <stdio.h>
int main(int argc, char **argv) {
    if(argc != 2) return 2;
    void *h=dlopen(argv[1], RTLD_NOW | RTLD_LOCAL);
    if(!h) { fprintf(stderr,"LOAD FAILED: %s\n",dlerror()); return 1; }
    const char *names[]={"autosuspend_enable","autosuspend_disable","autosuspend_force_suspend","autosuspend_set_wakeup_callback"};
    for(unsigned i=0;i<4;i++) if(!dlsym(h,names[i])) {fprintf(stderr,"Missing %s\n",names[i]);return 1;}
    puts("PASS: library loads and all four public APIs resolve; no power APIs called");
    dlclose(h); return 0;
}
