// Installs one previously compiled R7 Picture Style payload. Experimental ABI.
// The user's installed Canon EDSDK supplies every native symbol and all data.
#import <Foundation/Foundation.h>
#import <AppKit/AppKit.h>
#include <dlfcn.h>
#import <CommonCrypto/CommonDigest.h>
#include <string.h>
typedef uint32_t U;
typedef void *Ref;
static U (*Init)(void),(*Term)(void),(*List)(Ref *),(*Count)(Ref,U *),(*Child)(Ref,int,Ref *);
static U (*Open)(Ref),(*Close)(Ref),(*Release)(Ref),(*PropSize)(Ref,U,int,U *,U *),(*Get)(Ref,U,int,U,void *);
static U (*NativeSize)(Ref,U,int,U *,U *),(*NativeGet)(Ref,U,int,U,void *),(*NativeSet)(Ref,U,int,U,const void *),(*Extend)(Ref,int);
static void *module;
static BOOL testedSDK(NSString *path){
 NSData *data=[NSData dataWithContentsOfFile:path];if(!data)return NO;
 unsigned char digest[CC_SHA256_DIGEST_LENGTH];CC_SHA256(data.bytes,(CC_LONG)data.length,digest);
 NSMutableString *hex=[NSMutableString string];for(int i=0;i<CC_SHA256_DIGEST_LENGTH;i++)[hex appendFormat:@"%02x",digest[i]];
 return [hex isEqualToString:@"35a425fc84460bac539eb051b921362c142dfcde966514b18249be8c393529ea"];
}

static void symbol(void *out,const char *name){void *f=dlsym(module,name);if(!f){fprintf(stderr,"Missing SDK symbol: %s\n",name);exit(2);}memcpy(out,&f,sizeof(f));}
static void emit(NSDictionary *d){NSData *j=[NSJSONSerialization dataWithJSONObject:d options:0 error:nil];puts([[NSString alloc]initWithData:j encoding:NSUTF8StringEncoding].UTF8String);fflush(stdout);}
static NSData *readProp(Ref camera,U prop,int param){
 U type=0,n=0;U rc=PropSize(camera,prop,param,&type,&n);BOOL native=NO;
 if(rc==9&&(prop==0x01000001||prop==0x01000210||prop==0x01000203)){native=YES;rc=NativeSize(camera,prop,param,&type,&n);}
 if(rc||!n||n>1048576){emit(@{@"event":@"size_error",@"property":@(prop),@"param":@(param),@"rc":@(rc),@"bytes":@(n)});return nil;}
 NSMutableData *d=[NSMutableData dataWithLength:n];rc=(native?NativeGet:Get)(camera,prop,param,n,d.mutableBytes);
 if(rc){emit(@{@"event":@"read_error",@"property":@(prop),@"param":@(param),@"rc":@(rc)});return nil;}
 return d;
}
static NSData *file(NSString *dir,U prop,int param){return [NSData dataWithContentsOfFile:[dir stringByAppendingPathComponent:[NSString stringWithFormat:@"property-%08x-param-%d.bin",prop,param]]];}
static BOOL save(NSData *d,NSString *dir,U prop,int param){return [d writeToFile:[dir stringByAppendingPathComponent:[NSString stringWithFormat:@"property-%08x-param-%d.bin",prop,param]] atomically:YES];}
int main(int argc,const char **argv){@autoreleasepool{
 if(argc!=6){fprintf(stderr,"usage: eds_install_one SDK-path SNAPSHOT-dir SLOT(1-3) PAYLOAD.bin NEW-output-dir\n");return 2;}
 NSString *sdk=[NSString stringWithUTF8String:argv[1]],*snapshot=[NSString stringWithUTF8String:argv[2]],*out=[NSString stringWithUTF8String:argv[5]];
 int slot=atoi(argv[3]),param=slot+32;
 if(slot<1||slot>3||[[NSFileManager defaultManager]fileExistsAtPath:out]){fprintf(stderr,"Invalid slot or output directory already exists\n");return 2;}
 NSData *payload=[NSData dataWithContentsOfFile:[NSString stringWithUTF8String:argv[4]]];
 NSData *model=file(snapshot,0x01000001,0),*desc=file(snapshot,0x01000210,0);
 NSData *old=file(snapshot,0x01000203,param),*control=file(snapshot,0x114,param),*settings=file(snapshot,0x115,param);
 const U r7=0x80000464;U modelID=0,controlID=0;
 if(model.length==4)memcpy(&modelID,model.bytes,4);if(control.length==4)memcpy(&controlID,control.bytes,4);
 if(modelID!=r7||desc.length!=15076||payload.length!=83076||old.length!=83076||controlID!=64+slot||settings.length!=32){fprintf(stderr,"Snapshot, initialized slot or payload failed R7 preflight\n");return 2;}
 if(!testedSDK(sdk)){fprintf(stderr,"EDSDK version differs from the tested build\n");return 2;}
 NSString *framework=[[[sdk stringByDeletingLastPathComponent]stringByDeletingLastPathComponent]stringByDeletingLastPathComponent];
 NSError *loadError=nil;[[NSBundle bundleWithPath:framework]loadAndReturnError:&loadError];
 if(loadError){emit(@{@"event":@"bundle_error",@"error":loadError.description});return 2;}
 module=dlopen(argv[1],RTLD_NOW|RTLD_LOCAL);if(!module){fprintf(stderr,"%s\n",dlerror());return 2;}
 symbol(&Init,"EdsInitializeSDK");symbol(&Term,"EdsTerminateSDK");symbol(&List,"EdsGetCameraList");symbol(&Count,"EdsGetChildCount");symbol(&Child,"EdsGetChildAtIndex");symbol(&Open,"EdsOpenSession");symbol(&Close,"EdsCloseSession");symbol(&Release,"EdsRelease");
 symbol(&PropSize,"EdsGetPropertySize");symbol(&Get,"EdsGetPropertyData");
 symbol(&NativeSize,"_ZN10CPtpCamera15GetPropertySizeEjiP11EdsDataTypePj");symbol(&NativeGet,"_ZN10CPtpCamera15GetPropertyDataEjijPv");
 symbol(&NativeSet,"_ZN10CEdsObject15SetPropertyDataEjijPKv");symbol(&Extend,"_ZN10CPtpCamera19ExtendShutDownTimerEi");
 [NSApplication sharedApplication];U rc=Init();if(rc){emit(@{@"event":@"initialize_error",@"rc":@(rc)});return 1;}
 Ref list=NULL,camera=NULL;BOOL opened=NO;int result=1;
 @try{
  [[NSRunLoop currentRunLoop]runUntilDate:[NSDate dateWithTimeIntervalSinceNow:3]];
  rc=List(&list);U count=0;if(!rc&&list)rc=Count(list,&count);
  if(rc||count!=1){emit(@{@"event":@"camera_count_error",@"rc":@(rc),@"count":@(count)});return 1;}
  rc=Child(list,0,&camera);if(rc||!camera)return 1;
  rc=Open(camera);if(rc){emit(@{@"event":@"open_error",@"rc":@(rc)});return 1;}opened=YES;
  NSData *liveModel=readProp(camera,0x01000001,0),*liveDesc=readProp(camera,0x01000210,0);
  NSData *liveOld=readProp(camera,0x01000203,param),*liveControl=readProp(camera,0x114,param),*liveSettings=readProp(camera,0x115,param);
  if(![liveModel isEqualToData:model]||![liveDesc isEqualToData:desc]||![liveOld isEqualToData:old]||![liveControl isEqualToData:control]||![liveSettings isEqualToData:settings]){emit(@{@"event":@"snapshot_mismatch",@"slot":@(slot)});return 1;}
  NSError *err=nil;if(![[NSFileManager defaultManager]createDirectoryAtPath:out withIntermediateDirectories:YES attributes:nil error:&err])return 1;
  if(!save(liveModel,out,0x01000001,0)||!save(liveDesc,out,0x01000210,0)||!save(liveOld,out,0x01000203,param)||!save(liveControl,out,0x114,param)||!save(liveSettings,out,0x115,param)){emit(@{@"event":@"backup_failed"});return 1;}
  if([payload isEqualToData:liveOld]){emit(@{@"event":@"already_installed",@"slot":@(slot)});result=0;return result;}
  rc=Extend(camera,0);if(rc){emit(@{@"event":@"keep_awake_error",@"rc":@(rc)});return 1;}
  [[NSRunLoop currentRunLoop]runUntilDate:[NSDate dateWithTimeIntervalSinceNow:1]];
  rc=NativeSet(camera,0x01000203,param,(U)payload.length,payload.bytes);
  emit(@{@"event":@"write",@"slot":@(slot),@"rc":@(rc)});
  if(!rc){[[NSRunLoop currentRunLoop]runUntilDate:[NSDate dateWithTimeIntervalSinceNow:1]];
   NSData *after=readProp(camera,0x01000203,param),*afterControl=readProp(camera,0x114,param),*afterSettings=readProp(camera,0x115,param);
   if([after isEqualToData:payload]&&[afterControl isEqualToData:control]&&[afterSettings isEqualToData:settings]&&save(after,out,0x01000203,param)){
    emit(@{@"event":@"verified",@"slot":@(slot),@"readbackExact":@YES,@"settingsUnchanged":@YES});result=0;
   }
  }
  if(result){Extend(camera,0);U restore=NativeSet(camera,0x01000203,param,(U)old.length,old.bytes);
   NSData *restored=readProp(camera,0x01000203,param);
   emit(@{@"event":@"rollback",@"slot":@(slot),@"rc":@(restore),@"readbackExact":@([restored isEqualToData:old])});}
 }@finally{if(opened)Close(camera);if(camera)Release(camera);if(list)Release(list);Term();}
 return result;
}}
