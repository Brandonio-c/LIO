void setup(){ analogRead(A7); DDRC = 0x3F; }
void loop(){ PORTC = 0x3F; delay(10000); PORTC = 0x00; delay(10000); }
