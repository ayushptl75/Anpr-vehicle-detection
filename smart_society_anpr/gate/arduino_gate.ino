/*
  Smart Society ANPR Security Gate System - Arduino Hardware Controller
  Phase 15: Servo Motor, Barrier Relay, Green LED, Red LED Controller
  
  Pin Connections:
  - Servo Signal Pin: Pin 9 (0° = Gate CLOSED, 90° = Gate OPEN)
  - Barrier Relay Pin: Pin 8 (HIGH = Barrier Active / OPEN)
  - Green LED Pin: Pin 7 (HIGH = ACCESS ALLOWED)
  - Red LED Pin: Pin 6 (HIGH = ACCESS DENIED / Standby CLOSED)
  - Serial Baud Rate: 9600
*/

#include <Servo.h>

const int SERVO_PIN = 9;
const int RELAY_PIN = 8;
const int GREEN_LED_PIN = 7;
const int RED_LED_PIN = 6;

Servo gateServo;
String inputString = "";
bool stringComplete = false;

void openGateHardware() {
  digitalWrite(GREEN_LED_PIN, HIGH);
  digitalWrite(RED_LED_PIN, LOW);
  digitalWrite(RELAY_PIN, HIGH);
  gateServo.write(90); // Raise Barrier Arm to 90 degrees
}

void closeGateHardware() {
  digitalWrite(GREEN_LED_PIN, LOW);
  digitalWrite(RED_LED_PIN, HIGH);
  digitalWrite(RELAY_PIN, LOW);
  gateServo.write(0); // Lower Barrier Arm to 0 degrees
}

void deniedGateHardware() {
  digitalWrite(GREEN_LED_PIN, LOW);
  digitalWrite(RED_LED_PIN, HIGH);
  digitalWrite(RELAY_PIN, LOW);
  gateServo.write(0); // Keep Barrier Arm strictly CLOSED
}

void setup() {
  Serial.begin(9600);
  inputString.reserve(64);
  
  pinMode(RELAY_PIN, OUTPUT);
  pinMode(GREEN_LED_PIN, OUTPUT);
  pinMode(RED_LED_PIN, OUTPUT);
  
  gateServo.attach(SERVO_PIN);
  
  // Initial Standby State: Gate CLOSED, Red LED ON, Green LED OFF, Relay LOW
  closeGateHardware();
  Serial.println("ARDUINO_ANPR_GATE_READY");
}

void loop() {
  if (stringComplete) {
    inputString.trim();
    inputString.toUpperCase();

    if (inputString == "OPEN" || inputString == "ALLOW") {
      openGateHardware();
      Serial.println("STATUS:GATE_OPENED");
    } else if (inputString == "CLOSE") {
      closeGateHardware();
      Serial.println("STATUS:GATE_CLOSED");
    } else if (inputString == "DENIED") {
      deniedGateHardware();
      Serial.println("STATUS:GATE_DENIED");
    }

    inputString = "";
    stringComplete = false;
  }
}

void serialEvent() {
  while (Serial.available()) {
    char inChar = (char)Serial.read();
    if (inChar == '\n' || inChar == '\r') {
      stringComplete = true;
    } else {
      inputString += inChar;
    }
  }
}
