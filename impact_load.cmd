setMode -bscan
setCable -port auto
identify -inferir
identifyMPM

assignFile -p 1 -file soc-lx9_microboard.bit
program -p 1 

quit
