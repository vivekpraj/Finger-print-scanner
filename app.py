import streamlit as st
import threading
import av
import cv2
import numpy as np
from pathlib import Path
from datetime import datetime

from streamlit_webrtc import webrtc_streamer, RTCConfiguration, VideoTransformerBase

from utils.db_utils import init_db, get_connection
from utils.file_utils import save_image_bytes, make_zip_for_user

st.set_page_config(page_title="Fingerprint Capture", layout="centered")
init_db()

RTC_CONF = RTCConfiguration({"iceServers":[{"urls":["stun:stun.l.google.com:19302"]}]})

# Custom CSS for compact layout
st.markdown("""
<style>
    .stApp {
        max-width: 100%;
    }
    .main .block-container {
        padding-top: 1rem;
        padding-bottom: 1rem;
        max-width: 100%;
    }
    h1 {
        font-size: 1.5rem !important;
        margin-bottom: 0.5rem !important;
    }
    h3 {
        font-size: 1.1rem !important;
        margin-top: 0.3rem !important;
        margin-bottom: 0.3rem !important;
    }
    .stTextInput, .stSelectbox, .stTextArea {
        margin-bottom: 0.5rem !important;
    }
    .stButton button {
        height: 3rem;
        font-size: 1.1rem;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

st.title("📸 Fingerprint Capture")

# Compact form inputs
col_name, col_gender = st.columns([2, 1])
with col_name:
    name = st.text_input("Name", label_visibility="collapsed", placeholder="Enter Name")
with col_gender:
    gender = st.selectbox("Gender", ["Male", "Female", "Other"], label_visibility="collapsed")

# The required capture order
capture_order = [
    f"{finger}_{phase}"
    for finger in ["L1","L2","L3","L4","L5","R1","R2","R3","R4","R5"]
    for phase in ["center","left","right"]
]

# Finger names mapping
finger_names = {
    "L1": "Left Thumb", "L2": "Left Index", "L3": "Left Middle", 
    "L4": "Left Ring", "L5": "Left Pinky",
    "R1": "Right Thumb", "R2": "Right Index", "R3": "Right Middle", 
    "R4": "Right Ring", "R5": "Right Pinky"
}

# Phase names mapping
phase_names = {
    "center": "Center",
    "left": "Left Roll",
    "right": "Right Roll"
}

if "captures" not in st.session_state:
    st.session_state.captures = {}

if "capture_index" not in st.session_state:
    st.session_state.capture_index = 0

if "camera_facing" not in st.session_state:
    st.session_state.camera_facing = "user"  # "user" for front, "environment" for back


class FingerGuideCam(VideoTransformerBase):
    def __init__(self):
        self.frame_lock = threading.Lock()
        self.latest_frame = None
        self.current_instruction = ""

    def set_instruction(self, instruction):
        self.current_instruction = instruction

    def recv(self, frame: av.VideoFrame) -> av.VideoFrame:
        img = frame.to_ndarray(format="bgr24")
        h, w = img.shape[:2]

        out = img.copy()

        # Draw smaller centered guide box for finger placement
        box_width = int(w * 0.35)  # Smaller box
        box_height = int(h * 0.45)
        center_x = w // 2
        center_y = h // 2
        
        top_left = (center_x - box_width // 2, center_y - box_height // 2)
        bottom_right = (center_x + box_width // 2, center_y + box_height // 2)
        
        # Draw guide box with thick green border
        cv2.rectangle(out, top_left, bottom_right, (0, 255, 0), 4)
        
        # Add semi-transparent overlay outside the box
        overlay = out.copy()
        cv2.rectangle(overlay, (0, 0), (w, h), (0, 0, 0), -1)
        cv2.rectangle(overlay, top_left, bottom_right, (0, 255, 0), -1)
        out = cv2.addWeighted(out, 0.7, overlay, 0.3, 0)
        
        # Re-draw the guide box clearly
        cv2.rectangle(out, top_left, bottom_right, (0, 255, 0), 4)
        
        # Display instruction text at the top
        if self.current_instruction:
            text = self.current_instruction
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 0.8
            thickness = 2
            
            # Get text size for background
            (text_w, text_h), baseline = cv2.getTextSize(text, font, font_scale, thickness)
            
            # Draw background rectangle for text
            text_x = (w - text_w) // 2
            text_y = 40
            cv2.rectangle(out, (text_x - 10, text_y - text_h - 10), 
                         (text_x + text_w + 10, text_y + 10), (0, 0, 0), -1)
            
            # Draw text
            cv2.putText(out, text, (text_x, text_y), font, font_scale, (0, 255, 0), thickness)
        
        # Add "Place finger inside box" instruction
        instruction = "Place finger inside the green box"
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.6
        thickness = 2
        (text_w, text_h), _ = cv2.getTextSize(instruction, font, font_scale, thickness)
        text_x = (w - text_w) // 2
        text_y = bottom_right[1] + 40
        
        cv2.rectangle(out, (text_x - 10, text_y - text_h - 5), 
                     (text_x + text_w + 10, text_y + 5), (0, 0, 0), -1)
        cv2.putText(out, instruction, (text_x, text_y), font, font_scale, (255, 255, 255), thickness)

        with self.frame_lock:
            self.latest_frame = out.copy()

        return av.VideoFrame.from_ndarray(out, format="bgr24")


webrtc_ctx = webrtc_streamer(
    key=f"outline_cam_{st.session_state.camera_facing}",
    video_processor_factory=FingerGuideCam,
    rtc_configuration=RTC_CONF,
    media_stream_constraints={
        "video": {
            "facingMode": st.session_state.camera_facing
        }, 
        "audio": False
    }
)

# Camera switch button right below the video
col_switch1, col_switch2, col_switch3 = st.columns([1, 2, 1])
with col_switch2:
    camera_label = "📱 Switch to Back Camera" if st.session_state.camera_facing == "user" else "🤳 Switch to Front Camera"
    if st.button(camera_label, use_container_width=True):
        st.session_state.camera_facing = "environment" if st.session_state.camera_facing == "user" else "user"
        st.rerun()

if name and gender:
    # Determine next required capture
    if st.session_state.capture_index < len(capture_order):
        next_capture = capture_order[st.session_state.capture_index]
        finger_label, phase = next_capture.split("_")
        
        # Update camera instruction
        if webrtc_ctx.video_processor:
            instruction = f"{finger_names[finger_label]} - {phase_names[phase]}"
            webrtc_ctx.video_processor.set_instruction(instruction)
        
        # Show current instruction compactly
        st.markdown(f"**📍 {finger_names[finger_label]} - {phase_names[phase]}** ({st.session_state.capture_index + 1}/30)")
        
    else:
        next_capture = None
        st.success("✅ All done!")

    # Capture button directly below camera - PROMINENT
    if next_capture:
        if st.button("📸 CAPTURE", use_container_width=True, type="primary", key="capture_btn"):
            if webrtc_ctx.video_processor:
                proc: FingerGuideCam = webrtc_ctx.video_processor
                with proc.frame_lock:
                    frame = proc.latest_frame.copy() if proc.latest_frame is not None else None

                if frame is None:
                    st.error("⚠️ Camera not ready")
                else:
                    # Get the original frame dimensions
                    h, w = frame.shape[:2]
                    
                    # Calculate the green box coordinates (same as in FingerGuideCam)
                    box_width = int(w * 0.35)
                    box_height = int(h * 0.45)
                    center_x = w // 2
                    center_y = h // 2
                    
                    x1 = center_x - box_width // 2
                    y1 = center_y - box_height // 2
                    x2 = center_x + box_width // 2
                    y2 = center_y + box_height // 2
                    
                    # Crop only the green box area
                    cropped_frame = frame[y1:y2, x1:x2]
                    
                    success, buf = cv2.imencode(".png", cropped_frame)
                    if success:
                        st.session_state.captures[next_capture] = buf.tobytes()
                        st.session_state.capture_index += 1
                        st.success(f"✅ {next_capture}")
                        st.rerun()
                    else:
                        st.error("❌ Failed!")

    # Expandable section for completed captures
    with st.expander(f"✅ Completed: {len(st.session_state.captures)}/30", expanded=False):
        if st.session_state.captures:
            # Group by finger
            completed_by_finger = {}
            for key in st.session_state.captures:
                finger_label, phase = key.split("_")
                if finger_label not in completed_by_finger:
                    completed_by_finger[finger_label] = []
                completed_by_finger[finger_label].append(phase)
            
            # Display in organized format
            for finger_label in ["L1","L2","L3","L4","L5","R1","R2","R3","R4","R5"]:
                if finger_label in completed_by_finger:
                    phases = completed_by_finger[finger_label]
                    phases_str = ", ".join([phase_names[p] for p in sorted(phases)])
                    st.write(f"**{finger_names[finger_label]}**: {phases_str}")

    # After all 30 are captured → allow saving
    if st.session_state.capture_index == len(capture_order):
        if st.button("💾 Save & Download ZIP", use_container_width=True, type="primary", key="save_btn"):
            with st.spinner("Saving..."):
                conn = get_connection()
                c = conn.cursor()

                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                
                # Get extra info if it exists in session state
                extra = st.session_state.get('extra_info', '')
                
                c.execute(
                    "INSERT INTO users (name, gender, extra, timestamp) VALUES (?,?,?,?)",
                    (name, gender, extra, ts)
                )
                user_id = c.lastrowid
                conn.commit()

                folder = f"user_{user_id}_{name.replace(' ', '_')}_{ts}"

                for key, bts in st.session_state.captures.items():
                    filename = f"{key}.png"
                    save_image_bytes(folder, filename, bts)

                    finger_label, phase = key.split("_")
                    idx = {"center": 1, "left": 2, "right": 3}.get(phase, 0)

                    c.execute(
                        "INSERT INTO captures (user_id, finger_label, capture_idx, file_path) VALUES (?,?,?,?)",
                        (user_id, finger_label, idx, str(Path('data')/folder/filename))
                    )
                conn.commit()

                zip_path = make_zip_for_user(folder)

                with open(zip_path, "rb") as f:
                    st.download_button(
                        label="⬇️ Download ZIP",
                        data=f,
                        file_name=zip_path.name,
                        mime="application/zip",
                        use_container_width=True
                    )

                st.success("✅ Saved!")
                
                # Reset for next user
                if st.button("🔄 New Capture", use_container_width=True):
                    st.session_state.capture_index = 0
                    st.session_state.captures = {}
                    st.rerun()
else:
    st.info("ℹ️ Enter Name and Gender to begin")