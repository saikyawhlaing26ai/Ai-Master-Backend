from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import os
import subprocess
import uuid

app = FastAPI()

# Allow Frontend (GitHub Pages) to connect to this Backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def home():
    return {"status": "AI Master Backend Engine is Running!"}

@app.post("/render")
async def render_video(
    video: UploadFile = File(...),
    gemini_key: str = Form(...),
    tts_voice: str = Form("male"),
    blur_pos: int = Form(85)
):
    # ဖိုင်နာမည် အသစ်တစ်ခု ဖန်တီးခြင်း
    task_id = str(uuid.uuid4())[:8]
    input_video = f"temp_in_{task_id}.mp4"
    output_video = f"temp_out_{task_id}.mp4"

    # ၁။ User တင်လိုက်တဲ့ ဗီဒီယိုကို ဆာဗာပေါ် သိမ်းမယ်
    with open(input_video, "wb") as f:
        f.write(await video.read())

    # ၂။ (ဤနေရာတွင် STT, Gemini Translation, TTS အသံသွင်းခြင်း ကဏ္ဍများ ဆက်ရေးပါမည်)
    # လောလောဆယ် FFmpeg အလုပ်လုပ်/မလုပ် စမ်းသပ်ရန် ဗီဒီယိုကို 9:16 Crop လုပ်ပြီး Blur Band ထည့်မည့် Basic Render
    
    blur_y = int((blur_pos / 100) * 1280) # Assume 1280 height
    
    try:
        # ၃။ FFmpeg ဖြင့် တကယ့် Video အသစ် Burn-in လုပ်ခြင်း (Render Process)
        ffmpeg_cmd = [
            "ffmpeg", "-y", "-i", input_video,
            "-vf", f"scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280,drawbox=y={blur_y-40}:color=black@0.6:width=iw:height=80:t=fill",
            "-c:a", "copy",
            output_video
        ]
        
        subprocess.run(ffmpeg_cmd, check=True)

        # ၄။ ရလာတဲ့ ဗီဒီယိုအသစ်ကို Frontend ဆီ ပြန်ပို့ပေးခြင်း
        return FileResponse(output_video, media_type="video/mp4", filename=f"AiMaster_{task_id}.mp4")
    
    except Exception as e:
        return {"error": str(e)}
