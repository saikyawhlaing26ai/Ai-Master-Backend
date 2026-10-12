from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import os
import subprocess
import uuid

app = FastAPI()

app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"]
)

@app.get("/")
def home():
    return {"status": "AI Master Backend Engine V2 (Real Blur & AI Ready) is Running!"}

@app.post("/render")
async def render_video(
    video: UploadFile = File(...),
    gemini_key: str = Form(...),
    tts_voice: str = Form("male"),
    blur_pos: int = Form(85)
):
    task_id = str(uuid.uuid4())[:8]
    input_video = f"temp_in_{task_id}.mp4"
    output_video = f"temp_out_{task_id}.mp4"

    # ၁။ Video လက်ခံခြင်း
    with open(input_video, "wb") as f:
        f.write(await video.read())

    # ==========================================
    # (ယခုနေရာတွင် STT / Gemini / TTS API ချိတ်ဆက်မည့်
    # AI Processing Code များကို နောက်တစ်ဆင့်တွင် ဆက်ရေးပါမည်)
    # ==========================================
    
    # ၉:၁၆ ဘောင်အတွင်း Background Blur ပြုလုပ်ခြင်း နှင့် စာတန်းကို BoxBlur အစစ်ဖြင့် ဖျောက်ခြင်း
    blur_y = int((blur_pos / 100) * 1280)
    
    # Advanced FFmpeg Filter (Fit + Background Blur + Subtitle Real Blur)
    filter_complex = (
        f"[0:v]split=2[bg][fg];"
        f"[bg]scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280,boxblur=25:25[bg_blurred];"
        f"[fg]scale=720:1280:force_original_aspect_ratio=decrease[fg_scaled];"
        f"[bg_blurred][fg_scaled]overlay=(W-w)/2:(H-h)/2[merged];"
        f"[merged]split=2[m1][m2];"
        f"[m2]crop=720:120:0:{blur_y-60},boxblur=15:5[sub_blur];"
        f"[m1][sub_blur]overlay=0:{blur_y-60}[final]"
    )

    try:
        # Rendering Engine
        ffmpeg_cmd = [
            "ffmpeg", "-y", "-i", input_video,
            "-filter_complex", filter_complex,
            "-map", "[final]",
            "-map", "0:a?", # ယာယီအားဖြင့် မူရင်းအသံကို အရင်ပြန်ထည့်ထားမည် (နောက်တစ်ဆင့်တွင် TTS ဖြင့် အစားထိုးမည်)
            "-c:v", "libx264", "-preset", "fast",
            "-c:a", "aac",
            output_video
        ]
        
        subprocess.run(ffmpeg_cmd, check=True)

        return FileResponse(output_video, media_type="video/mp4", filename=f"AiMaster_Rendered_{task_id}.mp4")
    
    except Exception as e:
        return {"error": str(e)}

