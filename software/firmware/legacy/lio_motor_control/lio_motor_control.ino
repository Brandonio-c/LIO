// ############################################################################
// LEGACY — DO NOT FLASH THIS SKETCH ON THE CURRENT (LIO-ELEC-001 Rev A) WIRING
//
// Preserved unchanged below for reference (original:
// ~/Documents/Arduino/LIO-motor_control/LIO-motor_control.ino, Oct 2026).
// It predates the optical head electronics and is unsafe on today's board:
//   * D10 is configured INPUT_PULLUP as the UP button, but D10 is now CE2
//     (DRV2 enable, RAIL B) with a 10 k pull-down. The pin therefore reads
//     LOW ("pressed"): ~30 ms after EVERY reset or port open, the sketch
//     starts an unbounded synchronized UP move with no command sent
//     (observed 3 Nov 2026: "SYNC UP @ 500.00" right after the banner).
//     The internal pull-up also holds CE2 near 1 V, so the SWIR driver may
//     be partly enabled.
//   * It never clears the 74HC595s, which power up in random states, so an
//     arbitrary RAIL B channel may be selected while CE2 floats.
//   * Jogs target +/-2e9 steps and only end on "S": if USB drops, the motors
//     run with no limit (observed 2 Nov 2026). Coils stay energised.
// Use software/firmware/lio_firmware (v2): it accepts the same U/D/LU/LD/
// RU/RD/S/VA/VS/ACC commands as bounded jogs (docs/PROTOCOL.md §7).
// ############################################################################

#include <AccelStepper.h>

/*
  ============================================================
  LIO V3 - DUAL 28BYJ-48 Z AXIS CONTROLLER
  ============================================================

  LEFT ULN2003
    IN1 -> D2
    IN2 -> D3
    IN3 -> D4
    IN4 -> D5

  RIGHT ULN2003
    IN1 -> D6
    IN2 -> D7
    IN3 -> D8
    IN4 -> D9

  BUTTONS
    UP       -> D10 to GND
    DOWN     -> D11 to GND
    STOP     -> D12 to GND

  SERIAL COMMANDS
    U        synchronized UP
    D        synchronized DOWN

    LU       left UP
    LD       left DOWN

    RU       right UP
    RD       right DOWN

    S        STOP

    VAxxx    alignment speed
    VSxxx    synchronized speed
    ACCxxx   acceleration

    ?        help

  SPEED UNITS
    half-steps per second

  SAFETY
    No limit switches in this version.
    Supervised testing only.
*/

#define HALFSTEP 8

// AccelStepper ordering for the ULN2003 / 28BYJ-48.
AccelStepper leftMotor(
  HALFSTEP,
  2, 4, 3, 5
);

AccelStepper rightMotor(
  HALFSTEP,
  6, 8, 7, 9
);


// ------------------------------------------------------------
// BUTTONS
// ------------------------------------------------------------

const byte BUTTON_UP   = 10;
const byte BUTTON_DOWN = 11;
const byte BUTTON_STOP = 12;


// ------------------------------------------------------------
// DIRECTION
// ------------------------------------------------------------
//
// Start false.
//
// If synchronized motion makes the two screws physically
// rotate in opposite directions, change to true.
// ------------------------------------------------------------

bool reverseRightMotor = false;


// ------------------------------------------------------------
// SPEED SETTINGS
// ------------------------------------------------------------

float alignmentSpeed = 200.0;
float synchronizedSpeed = 500.0;
float acceleration = 250.0;


// ------------------------------------------------------------
// VERY LARGE TARGETS
// ------------------------------------------------------------
//
// These are only used to emulate continuous movement.
//
// They are NOT mechanical travel limits.
// ------------------------------------------------------------

const long FAR_POSITIVE = 2000000000L;
const long FAR_NEGATIVE = -2000000000L;


// ------------------------------------------------------------
// COMMAND STATE
// ------------------------------------------------------------

enum CommandState
{
  STOPPED,
  UP,
  DOWN
};

CommandState leftState = STOPPED;
CommandState rightState = STOPPED;


// ------------------------------------------------------------
// BUTTON DEBOUNCE
// ------------------------------------------------------------

const unsigned long DEBOUNCE_MS = 30;

bool lastUpReading = HIGH;
bool lastDownReading = HIGH;
bool lastStopReading = HIGH;

bool stableUpState = HIGH;
bool stableDownState = HIGH;
bool stableStopState = HIGH;

unsigned long upChangedAt = 0;
unsigned long downChangedAt = 0;
unsigned long stopChangedAt = 0;


// ============================================================
// CONFIGURATION
// ============================================================

void applyLeftSettings(float speedValue)
{
  leftMotor.setMaxSpeed(speedValue);
  leftMotor.setAcceleration(acceleration);
}


void applyRightSettings(float speedValue)
{
  rightMotor.setMaxSpeed(speedValue);
  rightMotor.setAcceleration(acceleration);
}


void applyBothSettings(float speedValue)
{
  applyLeftSettings(speedValue);
  applyRightSettings(speedValue);
}


// ============================================================
// STOP
// ============================================================

void stopAll()
{
  leftMotor.stop();
  rightMotor.stop();

  leftState = STOPPED;
  rightState = STOPPED;

  Serial.println("STOP");
}


// ============================================================
// LEFT MOTOR
// ============================================================

void leftUp()
{
  applyLeftSettings(alignmentSpeed);

  leftMotor.moveTo(FAR_POSITIVE);

  leftState = UP;

  Serial.println("LEFT UP");
}


void leftDown()
{
  applyLeftSettings(alignmentSpeed);

  leftMotor.moveTo(FAR_NEGATIVE);

  leftState = DOWN;

  Serial.println("LEFT DOWN");
}


// ============================================================
// RIGHT MOTOR
// ============================================================

void rightUp()
{
  applyRightSettings(alignmentSpeed);

  if (reverseRightMotor)
  {
    rightMotor.moveTo(FAR_NEGATIVE);
  }
  else
  {
    rightMotor.moveTo(FAR_POSITIVE);
  }

  rightState = UP;

  Serial.println("RIGHT UP");
}


void rightDown()
{
  applyRightSettings(alignmentSpeed);

  if (reverseRightMotor)
  {
    rightMotor.moveTo(FAR_POSITIVE);
  }
  else
  {
    rightMotor.moveTo(FAR_NEGATIVE);
  }

  rightState = DOWN;

  Serial.println("RIGHT DOWN");
}


// ============================================================
// SYNCHRONIZED MOTION
// ============================================================

void syncUp()
{
  applyBothSettings(synchronizedSpeed);

  leftMotor.moveTo(FAR_POSITIVE);

  if (reverseRightMotor)
  {
    rightMotor.moveTo(FAR_NEGATIVE);
  }
  else
  {
    rightMotor.moveTo(FAR_POSITIVE);
  }

  leftState = UP;
  rightState = UP;

  Serial.print("SYNC UP @ ");
  Serial.println(synchronizedSpeed);
}


void syncDown()
{
  applyBothSettings(synchronizedSpeed);

  leftMotor.moveTo(FAR_NEGATIVE);

  if (reverseRightMotor)
  {
    rightMotor.moveTo(FAR_POSITIVE);
  }
  else
  {
    rightMotor.moveTo(FAR_NEGATIVE);
  }

  leftState = DOWN;
  rightState = DOWN;

  Serial.print("SYNC DOWN @ ");
  Serial.println(synchronizedSpeed);
}


// ============================================================
// BUTTONS
// ============================================================

void updateButtons()
{
  const unsigned long now = millis();

  const bool upReading = digitalRead(BUTTON_UP);
  const bool downReading = digitalRead(BUTTON_DOWN);
  const bool stopReading = digitalRead(BUTTON_STOP);


  // UP
  if (upReading != lastUpReading)
  {
    upChangedAt = now;
    lastUpReading = upReading;
  }

  if ((now - upChangedAt) >= DEBOUNCE_MS)
  {
    if (upReading != stableUpState)
    {
      stableUpState = upReading;

      if (stableUpState == LOW)
      {
        syncUp();
      }
    }
  }


  // DOWN
  if (downReading != lastDownReading)
  {
    downChangedAt = now;
    lastDownReading = downReading;
  }

  if ((now - downChangedAt) >= DEBOUNCE_MS)
  {
    if (downReading != stableDownState)
    {
      stableDownState = downReading;

      if (stableDownState == LOW)
      {
        syncDown();
      }
    }
  }


  // STOP
  if (stopReading != lastStopReading)
  {
    stopChangedAt = now;
    lastStopReading = stopReading;
  }

  if ((now - stopChangedAt) >= DEBOUNCE_MS)
  {
    if (stopReading != stableStopState)
    {
      stableStopState = stopReading;

      if (stableStopState == LOW)
      {
        stopAll();
      }
    }
  }
}


// ============================================================
// SERIAL COMMAND BUFFER
// ============================================================

String serialBuffer = "";


// ============================================================
// SERIAL PROCESSING
// ============================================================

void processSerial()
{
  while (Serial.available() > 0)
  {
    char c = Serial.read();

    if (c == '\r')
    {
      continue;
    }


    if (c == '\n')
    {
      serialBuffer.trim();

      if (serialBuffer.length() == 0)
      {
        serialBuffer = "";
        continue;
      }

      String cmd = serialBuffer;


      // --------------------------------------------
      // STOP
      // --------------------------------------------

      if (cmd == "S" || cmd == "s")
      {
        stopAll();
      }


      // --------------------------------------------
      // SYNCHRONIZED
      // --------------------------------------------

      else if (cmd == "U" || cmd == "u")
      {
        syncUp();
      }

      else if (cmd == "D" || cmd == "d")
      {
        syncDown();
      }


      // --------------------------------------------
      // INDIVIDUAL LEFT
      // --------------------------------------------

      else if (cmd == "LU" || cmd == "lu")
      {
        leftUp();
      }

      else if (cmd == "LD" || cmd == "ld")
      {
        leftDown();
      }


      // --------------------------------------------
      // INDIVIDUAL RIGHT
      // --------------------------------------------

      else if (cmd == "RU" || cmd == "ru")
      {
        rightUp();
      }

      else if (cmd == "RD" || cmd == "rd")
      {
        rightDown();
      }


      // --------------------------------------------
      // ALIGNMENT SPEED
      //
      // Example:
      // VA300
      // --------------------------------------------

      else if (
        cmd.startsWith("VA") ||
        cmd.startsWith("va")
      )
      {
        const float value =
          cmd.substring(2).toFloat();

        if (value >= 50 && value <= 1500)
        {
          alignmentSpeed = value;

          Serial.print("ALIGN SPEED = ");
          Serial.println(alignmentSpeed);

          // If currently moving an individual motor,
          // update it immediately.
          if (leftState != STOPPED && rightState == STOPPED)
          {
            leftMotor.setMaxSpeed(alignmentSpeed);
          }

          if (rightState != STOPPED && leftState == STOPPED)
          {
            rightMotor.setMaxSpeed(alignmentSpeed);
          }
        }
        else
        {
          Serial.println(
            "ALIGNMENT SPEED RANGE: 50-1500"
          );
        }
      }


      // --------------------------------------------
      // SYNCHRONIZED SPEED
      //
      // Example:
      // VS1200
      // --------------------------------------------

      else if (
        cmd.startsWith("VS") ||
        cmd.startsWith("vs")
      )
      {
        const float value =
          cmd.substring(2).toFloat();

        if (value >= 100 && value <= 3000)
        {
          synchronizedSpeed = value;

          Serial.print("SYNC SPEED = ");
          Serial.println(synchronizedSpeed);

          // Update active synchronized motion.
          if (
            leftState != STOPPED &&
            rightState != STOPPED &&
            leftState == rightState
          )
          {
            leftMotor.setMaxSpeed(
              synchronizedSpeed
            );

            rightMotor.setMaxSpeed(
              synchronizedSpeed
            );
          }
        }
        else
        {
          Serial.println(
            "SYNC SPEED RANGE: 100-3000"
          );
        }
      }


      // --------------------------------------------
      // ACCELERATION
      //
      // Example:
      // ACC500
      // --------------------------------------------

      else if (
        cmd.startsWith("ACC") ||
        cmd.startsWith("acc")
      )
      {
        const float value =
          cmd.substring(3).toFloat();

        if (value >= 25 && value <= 3000)
        {
          acceleration = value;

          leftMotor.setAcceleration(
            acceleration
          );

          rightMotor.setAcceleration(
            acceleration
          );

          Serial.print("ACCELERATION = ");
          Serial.println(acceleration);
        }
        else
        {
          Serial.println(
            "ACCELERATION RANGE: 25-3000"
          );
        }
      }


      // --------------------------------------------
      // RESET POSITION COUNTERS
      // --------------------------------------------

      else if (
        cmd == "POSL0" ||
        cmd == "posl0"
      )
      {
        leftMotor.setCurrentPosition(0);

        Serial.println(
          "LEFT POSITION RESET TO 0"
        );
      }


      else if (
        cmd == "POSR0" ||
        cmd == "posr0"
      )
      {
        rightMotor.setCurrentPosition(0);

        Serial.println(
          "RIGHT POSITION RESET TO 0"
        );
      }


      // --------------------------------------------
      // HELP
      // --------------------------------------------

      else if (cmd == "?")
      {
        Serial.println();
        Serial.println(
          "LIO V3 Z AXIS COMMANDS"
        );
        Serial.println(
          "----------------------"
        );
        Serial.println(
          "U       synchronized UP"
        );
        Serial.println(
          "D       synchronized DOWN"
        );
        Serial.println(
          "LU      LEFT UP"
        );
        Serial.println(
          "LD      LEFT DOWN"
        );
        Serial.println(
          "RU      RIGHT UP"
        );
        Serial.println(
          "RD      RIGHT DOWN"
        );
        Serial.println(
          "S       STOP"
        );
        Serial.println(
          "VA200   alignment speed"
        );
        Serial.println(
          "VS500   synchronized speed"
        );
        Serial.println(
          "ACC250  acceleration"
        );
        Serial.println(
          "POSL0   reset left position"
        );
        Serial.println(
          "POSR0   reset right position"
        );
        Serial.println();
      }


      else
      {
        Serial.print(
          "UNKNOWN COMMAND: "
        );

        Serial.println(cmd);
      }


      serialBuffer = "";
    }


    else
    {
      serialBuffer += c;

      if (serialBuffer.length() > 32)
      {
        serialBuffer = "";
      }
    }
  }
}


// ============================================================
// SETUP
// ============================================================

void setup()
{
  Serial.begin(115200);


  // Buttons
  pinMode(
    BUTTON_UP,
    INPUT_PULLUP
  );

  pinMode(
    BUTTON_DOWN,
    INPUT_PULLUP
  );

  pinMode(
    BUTTON_STOP,
    INPUT_PULLUP
  );


  // Motors
  leftMotor.setMaxSpeed(
    synchronizedSpeed
  );

  rightMotor.setMaxSpeed(
    synchronizedSpeed
  );

  leftMotor.setAcceleration(
    acceleration
  );

  rightMotor.setAcceleration(
    acceleration
  );


  leftMotor.setCurrentPosition(0);
  rightMotor.setCurrentPosition(0);


  leftState = STOPPED;
  rightState = STOPPED;


  Serial.println();
  Serial.println(
    "=============================="
  );
  Serial.println(
    "LIO V3 Z AXIS READY"
  );
  Serial.println(
    "=============================="
  );
  Serial.print(
    "Alignment speed = "
  );
  Serial.println(alignmentSpeed);

  Serial.print(
    "Sync speed = "
  );
  Serial.println(synchronizedSpeed);

  Serial.print(
    "Acceleration = "
  );
  Serial.println(acceleration);

  Serial.println();
}


// ============================================================
// MAIN LOOP
// ============================================================

void loop()
{
  updateButtons();

  processSerial();

  /*
    AccelStepper requires run() to be called frequently.
  */

  leftMotor.run();

  rightMotor.run();
}