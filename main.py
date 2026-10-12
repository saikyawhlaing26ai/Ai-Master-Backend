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
    return {"status": "AI Master Backend Engine V3 (Full UI Control) is Running!"}

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

    # ၁။ Video လက်ခံခြင်း
    with open(input_video, "wb") as f:
        f.write(await video.read())

    # ၂။ Canvas Ratio သတ်မှတ်ခြင်း (W:H)
    w, h = 720, 1280
    if ratio == "16:9":
        w, h = 1280, 720
    elif ratio == "1:1":
        w, h = 1080, 1080

    # ၃။ Color, Flip, Zoom, Pan သတ်မှတ်ခြင်း
    color_filter = f"eq=brightness={(bri-100)/100}:contrast={con/100}:saturation={sat/100}"
    flip_filter = "hflip," if flip.lower() == "true" else ""
    
    # ၄။ Inner Crop & Scale သတ်မှတ်ခြင်း
    # (ဤအပိုင်းသည် ရှုပ်ထွေးနိုင်သဖြင့် လောလောဆယ်တွင် UI ၏ Scale/Crop အတိုင်း အနီးစပ်ဆုံး ဖြစ်အောင် ရေးထားပါသည်)
    # Background Blur အတွက်
    bg_filter = f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},boxblur=15:15"
    
    # Foreground အတွက် Inner Crop ကို တွက်ချက်ခြင်း (ခန့်မှန်းခြေ)
    fg_crop_filter = ""
    if inner_crop != "none":
        # ဥပမာ - 3:4 ဆိုလျှင် w:h အချိုးကို တွက်ချက်၍ crop လုပ်မည်
        if inner_crop == "3:4":
            fg_crop_filter = "crop=ih*3/4:ih,"
        elif inner_crop == "16:9":
            fg_crop_filter = "crop=iw:iw*9/16,"
        elif inner_crop == "1:1":
            fg_crop_filter = "crop=min(iw\\,ih):min(iw\\,ih),"
        elif inner_crop == "4:5":
            fg_crop_filter = "crop=ih*4/5:ih,"
        elif inner_crop == "9:16":
             fg_crop_filter = "crop=ih*9/16:ih,"

    fg_filter = f"{flip_filter}{color_filter},{fg_crop_filter}scale={w*zoom}:{h*zoom}:force_original_aspect_ratio=decrease"
    
    # ၅။ Blur Position တွက်ချက်ခြင်း
    bY = int((blur_pos / 100) * h)
    bH = blur_height
    bTop = max(0, bY - (bH // 2))

    # ၆။ FFmpeg Filter Complex ရေးဆွဲခြင်း
    filter_complex = (
        f"[0:v]split=2[bg_src][fg_src];"
        f"[bg_src]{bg_filter}[bg];"
        f"[fg_src]{fg_filter}[fg];"
        # Background နှင့် Foreground ကို ပေါင်းခြင်း (Pan Y ကိုပါ ထည့်သွင်းစဉ်းစားသည်)
        f"[bg][fg]overlay=(W-w)/2:((H-h)/2)+{pan_y}[merged];"
        f"[merged]split=2[m1][m2];"
        # Blur Band ပြုလုပ်ခြင်း
        f"[m2]crop={w}:{bH}:0:{bTop},boxblur=15:5[sub_blur];"
        f"[m1][sub_blur]overlay=0:{bTop}[final]"
    )

    try:
        # Rendering Engine (ပိုမြန်အောင် ultrafast သုံးထားသည်)
        ffmpeg_cmd = [
            "ffmpeg", "-y", "-i", input_video,
            "-filter_complex", filter_complex,
            "-map", "[final]",
            "-map", "0:a?", 
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28", # မြန်ဆန်စေရန်
            "-c:a", "aac",
            output_video
        ]
        
        subprocess.run(ffmpeg_cmd, check=True)

        return FileResponse(output_video, media_type="video/mp4", filename=f"AiMaster_Rendered_{task_id}.mp4")
    
    except Exception as e:
        return {"error": str(e)}
    finally:
        # ယာယီဖိုင်များကို ရှင်းလင်းခြင်း (Storage မပြည့်စေရန်)
        if os.path.exists(input_video):
            os.remove(input_video)
        # output_video ကို FileResponse က ပြီးမှ ရှင်းလင်းမည်ဖြစ်၍ ဤနေရာတွင် မဖျက်ပါ
