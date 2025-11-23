import cv2
import mediapipe as mp
import time
#opening camera (0 for the default camera)

fingertips = [4, 8]

videoCap = cv2.VideoCapture(0)
lastFrameTime = 0
handSolution = mp.solutions.hands
hands = handSolution.Hands(max_num_hands=2,)
while True:
    #reading image
    success, img = videoCap.read()
    #showing image on separate window (only if read was successfull)
    if success:
        imgRGB = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        #fps calculations
        thisFrameTime = time.time()
        fps = 1 / (thisFrameTime - lastFrameTime)
        lastFrameTime = thisFrameTime
        #write on image fps
        cv2.putText(img, f'FPS:{int(fps)}',
                    (20, 70),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        #recognize hands from out image
        recHands = hands.process(img)
        if recHands.multi_hand_landmarks:
            for hand in recHands.multi_hand_landmarks:
                #draw the dots on each our image for vizual help
                for datapoint_id, point in enumerate(hand.landmark):
                    h, w, c = img.shape
                    x, y = int(point.x * w), int(point.y * h)

                    if datapoint_id in fingertips:
                        cv2.circle(img, (x, y),
                               10, (255, 0, 255)
                               , cv2.FILLED)


        cv2.imshow("CamOutput", img)
        cv2.waitKey(1)