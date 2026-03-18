import cv2 as cv
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from mediapipe.tasks.python.vision import drawing_utils
from mediapipe.tasks.python.vision import drawing_styles
import numpy as np
import time

# Setup Aliases
BaseOptions = python.BaseOptions
PoseLandmarker = vision.PoseLandmarker
PoseLandmarkerOptions = vision.PoseLandmarkerOptions
PoseLandmarkerResult = vision.PoseLandmarkerResult
VisionRunningMode = vision.RunningMode

# --- Global States ---
latest_annotated_frame = None
posture_status = "Initializing..."
current_metrics = {"gap": 0, "tilt": 0, "z_depth": 0}

# Calibration & Timer Globals
is_calibrated = False
calibration_data = []
thresholds = {"gap": 0.20, "z": -1.10} # Default fallbacks
bad_posture_start_time = None 
alert_active = False

def analyze_metrics(landmarks):
    if not landmarks: return 0, 0, 0
    left_gap = landmarks[11].y - landmarks[7].y
    right_gap = landmarks[12].y - landmarks[8].y
    avg_gap = (left_gap + right_gap) / 2
    shoulder_tilt = abs(landmarks[11].y - landmarks[12].y)
    nose_z = landmarks[0].z
    return avg_gap, shoulder_tilt, nose_z

def result_callback(result: PoseLandmarkerResult, output_image: mp.Image, timestamp_ms: int):
    global latest_annotated_frame, posture_status, current_metrics, is_calibrated, calibration_data, thresholds, bad_posture_start_time, alert_active
    
    frame_rgb = output_image.numpy_view()
    annotated_image = np.copy(frame_rgb)

    if result.pose_landmarks:
        pose_landmarks = result.pose_landmarks[0]
        gap, tilt, z_depth = analyze_metrics(pose_landmarks)
        current_metrics.update({"gap": gap, "tilt": tilt, "z_depth": z_depth})

        # --- STEP 2: AUTO-CALIBRATION LOGIC ---
        if not is_calibrated:
            posture_status = f"CALIBRATING... Hold Still ({len(calibration_data)}/30)"
            calibration_data.append((gap, z_depth))
            if len(calibration_data) >= 30:
                avg_cal_gap = sum(g for g, z in calibration_data) / 30
                avg_cal_z = sum(z for g, z in calibration_data) / 30
                # Set thresholds slightly more aggressive than baseline
                thresholds["gap"] = avg_cal_gap * 0.85 
                thresholds["z"] = avg_cal_z * 1.30 
                is_calibrated = True
        
        # --- STEP 1: DETECTION & TIMER LOGIC ---
        else:
            is_bad = (z_depth < thresholds["z"]) or (gap < thresholds["gap"]) or (tilt > 0.06)
            
            if is_bad:
                if bad_posture_start_time is None:
                    bad_posture_start_time = time.time()
                
                elapsed = time.time() - bad_posture_start_time
                if elapsed > 3.0:
                    posture_status = f"WARNING: FIX POSTURE! ({int(elapsed)}s)"
                    alert_active = True
                else:
                    posture_status = "Good (grace period)"
                    alert_active = False
            else:
                posture_status = "Good Posture"
                bad_posture_start_time = None
                alert_active = False

        # Draw skeleton
        drawing_utils.draw_landmarks(
            image=annotated_image, landmark_list=pose_landmarks,
            connections=vision.PoseLandmarksConnections.POSE_LANDMARKS,
            landmark_drawing_spec=drawing_styles.get_default_pose_landmarks_style()
        )
    
    latest_annotated_frame = cv.cvtColor(annotated_image, cv.COLOR_RGB2BGR)

def main():
    options = PoseLandmarkerOptions(
        base_options=BaseOptions(model_asset_path='pose_landmarker_full.task'),
        running_mode=VisionRunningMode.LIVE_STREAM,
        result_callback=result_callback)

    cap = cv.VideoCapture(0)

    with PoseLandmarker.create_from_options(options) as landmarker:
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret: break

            image_rgb = cv.cvtColor(frame, cv.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=image_rgb)
            landmarker.detect_async(mp_image, int(time.time() * 1000))
            
            display_frame = latest_annotated_frame if latest_annotated_frame is not None else frame
            
            # UI Styling
            text_color = (0, 0, 255) if alert_active else (0, 255, 0)
            if "CALIBRATING" in posture_status: text_color = (0, 255, 255) # Yellow

            cv.putText(display_frame, posture_status, (20, 50), 
                       cv.FONT_HERSHEY_SIMPLEX, 0.8, text_color, 2)
            
            cv.imshow('Smart Posture Tracker', display_frame)
            
            if cv.waitKey(1) & 0xFF == ord('q'): break

    cap.release()
    cv.destroyAllWindows()

if __name__ == '__main__':
    main()