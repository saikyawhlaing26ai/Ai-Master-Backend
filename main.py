from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import FileResponse, JSONResponse
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
    return {"status": "AI Master Backend Engine V6 (Even Number Fix) is Running!"}

# မဂဏန်းများကို စုံကိန်း (Even Number) အဖြစ် အလိုအလျောက် ပြောင်းပေးမည့် Function
def make_even(n):
    return int(n) // 2 * 2

@app.post("/render")
async def render_video(
    video: UploadFile = File(...),
    gemini_key: str = Form(None),
    tts_voice: str = Form("male"),
    ratio: str = Form("9:16"),
    inner_crop: str = Form("none"),
    blur_pos: int = Form(85),
    blur_height: int = Form(120),
    flip: str = Form("false"),
    zoom: float = Form(1.0),
    pan_y: int = Form(0),
    bri: int = Form(100),
    con: int = Form(100),
    sat: int = Form(100)
):
    task_id = str(uuid.uuid4())[:8]
    input_video = f"temp_in_{task_id}.mp4"
    output_video = f"temp_out_{task_id}.mp4"

    with open(input_video, "wb") as f:
        f.write(await video.read())

    try:
        w, h = 720, 1280
        if ratio == "16:9": w, h = 1280, 720
        elif ratio == "1:1": w, h = 1080, 1080

        color_filter = f"eq=brightness={(bri-100)/100.0}:contrast={con/100.0}:saturation={sat/100.0}"
        flip_filter = "hflip," if flip.lower() == "true" else ""
        
        bg_filter = f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},boxblur=15:15"
        
        fg_crop_filter = ""
        if inner_crop != "none":
            if inner_crop == "3:4": fg_crop_filter = "crop=ih*3/4:ih,"
            elif inner_crop == "16:9": fg_crop_filter = "crop=ih*16/9:ih,"
            elif inner_crop == "1:1": fg_crop_filter = "crop=min(iw\\,ih):min(iw\\,ih),"
            elif inner_crop == "4:5": fg_crop_filter = "crop=ih*4/5:ih,"
            elif inner_crop == "9:16": fg_crop_filter = "crop=ih*9/16:ih,"

        # Zoom တွက်ချက်မှုကြောင့် ထွက်လာမည့် Pixels များကို စုံကိန်းဖြစ်အောင် ထိန်းပေးခြင်း
        fg_w = make_even(w * zoom)
        fg_h = make_even(h * zoom)
        
        fg_filter = f"{flip_filter}{color_filter},{fg_crop_filter}scale={fg_w}:{fg_h}:force_original_aspect_ratio=decrease"
        
        # Blur ဧရိယာ တွက်ချက်မှုကို စုံကိန်းဖြစ်အောင် ထိန်းပေးခြင်း
        bY = int((blur_pos / 100.0) * h)
        bH = make_even(blur_height)
        bTop = make_even(max(0, bY - (bH // 2)))
        safe_pan = make_even(pan_y)

        # format=yuv420p ကို ထည့်သွင်းပေးခြင်းဖြင့် FFmpeg အရောင်စနစ် Error မတက်စေရန် ကာကွယ်ခြင်း
        filter_complex = (
            f"[0:v]split=2[bg_src][fg_src];"
            f"[bg_src]{bg_filter}[bg];"
            f"[fg_src]{fg_filter}[fg];"
            f"[bg][fg]overlay=(W-w)/2:((H-h)/2)+({safe_pan})[merged];"
            f"[merged]split=2[m1][m2];"
            f"[m2]crop={w}:{bH}:0:{bTop},boxblur=15:5[sub_blur];"
            f"[m1][sub_blur]overlay=0:{bTop},format=yuv420p[final]"
        )

        ffmpeg_cmd = [
            "ffmpeg", "-y", "-i", input_video,
            "-filter_complex", filter_complex,
            "-map", "[final]",
            "-map", "0:a?", 
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
            "-c:a", "aac",
            output_video
        ]
        
        process = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
        if process.returncode != 0:
            error_msg = process.stderr.split('\n')[-5:] 
            raise Exception(f"FFmpeg Failed: {' '.join(error_msg)}")

        return FileResponse(output_video, media_type="video/mp4", filename=f"AiMaster_Rendered_{task_id}.mp4")
    
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
    finally:
        if os.path.exists(input_video):
            os.remove(input_video)
