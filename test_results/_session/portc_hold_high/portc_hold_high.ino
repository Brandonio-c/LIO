// Nano off the breadboard: hold A0-A5 HIGH continuously for meter checks.
void setup(){ analogRead(A7); DDRC = 0x3F; PORTC = 0x3F; }
void loop(){}
