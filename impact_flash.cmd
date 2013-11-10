setMode -bscan
setCable -port auto
identify -inferir
identifyMPM

attachflash -position 1 -spi N25Q128
assignfiletoattachedflash -position 1 -file soc-lx9_microboard.mcs
# attachflash -position 1 -spi N25Q128
program -p 1 -dataWidth 4 -spionly -e -v -loadfpga

# readbackToFile -p 1 -file build/flash_readback.mcs -spionly
# saveCDF -file build/soc.cdf
# saveProjectFile -file build/soc.ipf

quit
