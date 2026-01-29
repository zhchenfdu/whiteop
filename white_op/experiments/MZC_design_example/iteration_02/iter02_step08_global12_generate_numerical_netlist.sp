.subckt opamp NodeInput NodeOutput NodeGround
*main amplification stages and associated parasitics
G_1 Node1 NodeGround NodeInput NodeGround 'G_1'
Rprs_1 Node1 NodeGround 'A_1/G_1'
Cprs_1 Node1 NodeGround 'G_2/6.28*5n'
G_2 NodeOutput NodeGround Node1 NodeGround 'G_2'
Rprs_2 NodeOutput NodeGround 'A_2/G_2'
*loads
C_L NodeOutput NodeGround 10p
R_L NodeOutput NodeGround 10Meg
*simple miller compensation
C_m Node1 NodeOutput 'C_m'
*feedforward gm stage
G_f NodeOutput NodeGround NodeInput NodeGround '-G_f'
Rprs_f NodeOutput NodeGround 'A_f/G_f'
.ends
