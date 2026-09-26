// Experimental native read-only getter for this installed SDK. No setter, private key,
// process injection or camera registration is used. Keep output private.
#import <Foundation/Foundation.h>
#import <AppKit/AppKit.h>
#include <dlfcn.h>
#import <CommonCrypto/CommonDigest.h>
typedef uint32_t U;
typedef void *Ref;
static U (*Init)(void),(*Term)(void),(*List)(Ref *),(*Count)(Ref,U *),(*Child)(Ref,int,Ref *);
static U (*Open)(Ref),(*Close)(Ref),(*Release)(Ref),(*PropSize)(Ref,U,int,U *,U *),(*Get)(Ref,U,int,U,void *);
static U (*NativeSize)(Ref,U,int,U *,U *),(*NativeGet)(Ref,U,int,U,void *);
static void *module;
static BOOL testedSDK(NSString *path){
 NSData *data=[NSData dataWithContentsOfFile:path];if(!data)return NO;
 unsigned char digest[CC_SHA256_DIGEST_LENGTH];CC_SHA256(data.bytes,(CC_LONG)data.length,digest);
 NSMutableString *hex=[NSMutableString string];for(int i=0;i<CC_SHA256_DIGEST_LENGTH;i++)[hex appendFormat:@"%02x",digest[i]];
 return [hex isEqualToString:@"35a425fc84460bac539eb051b921362c142dfcde966514b18249be8c393529ea"];
}

static void symbol(void *out,const char *name){void *f=dlsym(module,name);if(!f){fprintf(stderr,"Missing %s\n",name);exit(2);} memcpy(out,&f,sizeof(f));}
static void emit(NSDictionary *d){NSData *j=[NSJSONSerialization dataWithJSONObject:d options:0 error:nil];puts([[NSString alloc]initWithData:j encoding:NSUTF8StringEncoding].UTF8String);fflush(stdout);}
static void readProperty(Ref camera,U prop,int param,NSString *folder){
 U type=0,size=0; U rc=PropSize(camera,prop,param,&type,&size);
 BOOL native=NO;
 if(rc==9&&(prop==0x01000001||prop==0x01000210||prop==0x01000203)){
  native=YES;rc=NativeSize(camera,prop,param,&type,&size);
 }
 NSMutableDictionary *event=[@{@"native_getter":@(native),@"property":[NSString stringWithFormat:@"0x%08x",prop],@"parameter":@(param),@"size_rc":@(rc),@"size":@(size),@"data_type":@(type)} mutableCopy];
 if(!rc&&size>0&&size<=1048576){
  NSMutableData *data=[NSMutableData dataWithLength:size];rc=(native?NativeGet:Get)(camera,prop,param,size,data.mutableBytes);event[@"read_rc"]=@(rc);
  if(!rc){NSString *name=[NSString stringWithFormat:@"property-%08x-param-%d.bin",prop,param];
   event[@"saved"]=@([data writeToFile:[folder stringByAppendingPathComponent:name] atomically:YES]);event[@"file"]=name;}
 }
 emit(event);
}
int main(int argc,const char **argv){@autoreleasepool{
 if(argc!=3){fprintf(stderr,"usage: eds_read EDSDK-library NEW-output-directory\n");return 2;}
 NSString *folder=[NSString stringWithUTF8String:argv[2]];
 if([[NSFileManager defaultManager]fileExistsAtPath:folder]){fprintf(stderr,"Output directory must be new\n");return 2;}
 NSString *sdkPath=[NSString stringWithUTF8String:argv[1]];
 if(!testedSDK(sdkPath)){fprintf(stderr,"EDSDK version differs from the tested build\n");return 2;}
 NSString *frameworkPath=[[[sdkPath stringByDeletingLastPathComponent] stringByDeletingLastPathComponent] stringByDeletingLastPathComponent];
 NSError *loadError=nil; [[NSBundle bundleWithPath:frameworkPath] loadAndReturnError:&loadError];
 if(loadError)emit(@{@"event":@"bundle_load_error",@"error":loadError.description});
 module=dlopen(argv[1],RTLD_NOW|RTLD_LOCAL);if(!module){fprintf(stderr,"%s\n",dlerror());return 2;}
 symbol(&Init,"EdsInitializeSDK");symbol(&Term,"EdsTerminateSDK");symbol(&List,"EdsGetCameraList");symbol(&Count,"EdsGetChildCount");symbol(&Child,"EdsGetChildAtIndex");symbol(&Open,"EdsOpenSession");symbol(&Close,"EdsCloseSession");symbol(&Release,"EdsRelease");symbol(&PropSize,"EdsGetPropertySize");symbol(&Get,"EdsGetPropertyData");
 symbol(&NativeSize,"_ZN10CPtpCamera15GetPropertySizeEjiP11EdsDataTypePj");symbol(&NativeGet,"_ZN10CPtpCamera15GetPropertyDataEjijPv");
 [NSApplication sharedApplication];
 U rc=Init();emit(@{@"event":@"initialize",@"rc":@(rc)});if(rc)return 1;
 Ref list=NULL,camera=NULL;BOOL opened=NO;int result=1;
 @try{
  [[NSRunLoop currentRunLoop]runUntilDate:[NSDate dateWithTimeIntervalSinceNow:5]];
  rc=List(&list);if(rc||!list){emit(@{@"event":@"list_failed",@"rc":@(rc)});return 1;}
  U count=0;rc=Count(list,&count);emit(@{@"event":@"camera_count",@"rc":@(rc),@"count":@(count)});
  if(rc||count!=1)return 1;
  rc=Child(list,0,&camera);if(rc||!camera)return 1;
  rc=Open(camera);emit(@{@"event":@"open_session",@"rc":@(rc)});if(rc)return 1;opened=YES;
  NSError *error=nil;if(![[NSFileManager defaultManager]createDirectoryAtPath:folder withIntermediateDirectories:YES attributes:nil error:&error]){emit(@{@"event":@"directory_failed",@"error":error.description});return 1;}
  // Product name, firmware, camera/compiler inputs; then the three saved styles.
  for(NSNumber *prop in @[@2,@7,@0x01000001,@0x01000210]) readProperty(camera,prop.unsignedIntValue,0,folder);
  for(int param=33;param<=35;param++)for(NSNumber *prop in @[@0x114,@0x115,@0x01000203])readProperty(camera,prop.unsignedIntValue,param,folder);
  result=0;
 }@finally{if(opened)emit(@{@"event":@"close_session",@"rc":@(Close(camera))});if(camera)Release(camera);if(list)Release(list);emit(@{@"event":@"terminate",@"rc":@(Term())});}
 return result;
}}
