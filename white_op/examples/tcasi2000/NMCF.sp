.subckt opamp NodeInput NodeOutput NodeGround
*main amplification stages and associated parasitics
G_1 Node1 NodeGround NodeInput NodeGround 'G_1'
Rprs_1 Node1 NodeGround 'A_1/G_1'
Cprs_1 Node1 NodeGround 'G_2/6.28*5n'
G_2 Node2 NodeGround Node1 NodeGround '-1*G_2'
Rprs_2 Node2 NodeGround 'A_2/G_2'
Cprs_2 Node2 NodeGround 'G_3/6.28*5n'
G_3 NodeOutput NodeGround Node2 NodeGround 'G_3'
Rprs_2_out NodeOutput NodeGround 'A_3/G_3'
*loads
C_L NodeOutput NodeGround 10p
R_L NodeOutput NodeGround 10Meg
*simple nested miller compensation
C_m1 Node1 NodeOutput 'C_m1'
C_m2 Node2 NodeOutput 'C_m2'
*feedforward gm stage 2
G_f2 NodeOutput NodeGround Node1 NodeGround 'G_f2'
Rprs_f2 NodeOutput NodeGround 'A_f2/G_f2'
.ends
