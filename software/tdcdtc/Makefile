MSCDIR=../..
include $(MSCDIR)/software/common.mak

OBJECTS=isr.o main.o tdcdtc.o

all: tdcdtc.bin

# pull in dependency info for *existing* .o files
-include $(OBJECTS:.o=.d)

%.bin: %.elf
	$(OBJCOPY) -O binary $< $@
	chmod -x $@

tdcdtc.elf: $(OBJECTS) libs

%.elf:
	$(LD) $(LDFLAGS) \
		-T $(MSCDIR)/software/libbase/linker-sdram.ld \
		-N -o $@ \
		$(MSCDIR)/software/libbase/crt0.o \
		$(OBJECTS) \
		-L$(MSCDIR)/software/libbase \
		-L$(MSCDIR)/software/libcompiler-rt \
		-lbase -lcompiler-rt
	chmod -x $@

%.o: %.c
	$(compile-dep)

%.o: %.S
	$(assemble)

libs:
	$(MAKE) -C $(MSCDIR)/software/libcompiler-rt
	$(MAKE) -C $(MSCDIR)/software/libbase

load: tdcdtc.bin
	$(MAKE) -C $(MSCDIR)/tools
	$(MSCDIR)/tools/flterm --port /dev/ttyUSB0 --kernel tdcdtc.bin

clean:
	$(RM) $(OBJECTS) $(OBJECTS:.o=.d) tdcdtc.elf tdcdtc.bin
	$(RM) .*~ *~

.PHONY: all clean libs load
