.title Project: Three-Stage Opamp
.inc 'opamp.sp'
.inc 'param'

xac vin_ac vo_ac gnd opamp
vin vin_ac 0 ac=1

.OPTIONS INGOLD=0
.option post=2
.op
.ac dec 100 1 1g
.print vdb(vo_ac)
.print vp(vo_ac)
.meas ac gain find vdb(vo_ac) at=1
.meas ac ugf when vdb(vo_ac)=0
.meas ac phase FIND vp(vo_ac) at=ugf
.pz v(vo_ac) vin
.TEMP 27
.end