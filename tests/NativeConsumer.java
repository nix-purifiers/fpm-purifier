// SPDX-License-Identifier: MIT
import java.lang.foreign.*;
import java.lang.invoke.*;
import java.nio.file.*;
public class NativeConsumer {
 public static void main(String[] args) throws Throwable {
  Path expected=Path.of(args[0]).toRealPath();Linker linker=Linker.nativeLinker();
  try(Arena a=Arena.ofConfined()){
   SymbolLookup lookup=SymbolLookup.libraryLookup(expected,a);
   MemorySegment symbol=lookup.find("purifier_answer").orElseThrow();
   MethodHandle call=linker.downcallHandle(symbol,FunctionDescriptor.of(ValueLayout.JAVA_INT,ValueLayout.JAVA_INT));
   if((int)call.invokeExact(0)!=42||(int)call.invokeExact(1)!=43)throw new AssertionError("values");
   MemorySegment info=a.allocate(4*ValueLayout.ADDRESS.byteSize(),ValueLayout.ADDRESS.byteAlignment());
   MethodHandle origin=linker.downcallHandle(linker.defaultLookup().find("dladdr").orElseThrow(),FunctionDescriptor.of(ValueLayout.JAVA_INT,ValueLayout.ADDRESS,ValueLayout.ADDRESS));
   if((int)origin.invokeExact(symbol,info)==0)throw new AssertionError("dladdr");
   if(!Path.of(info.get(ValueLayout.ADDRESS,0).reinterpret(4096).getString(0)).toRealPath().equals(expected))throw new AssertionError("origin");
  }
  System.out.println("Java bind(C)42/43 +origin +scoped close +natural return passed");
 }
}
