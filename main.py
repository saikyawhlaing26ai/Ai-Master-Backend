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
    return {"status": "AI Master Backend Engine V5 (FFmpeg Fix) is Running!"}

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
        # ၁။ Canvas Ratio သတ်မှတ်ခြင်း (W:H)
        w, h = 720, 1280
        if ratio == "16:9": w, h = 1280, 720
        elif ratio == "1:1": w, h = 1080, 1080

        # ၂။ Color, Flip သတ်မှတ်ခြင်း
        color_filter = f"eq=brightness={(bri-100)/100.0}:contrast={con/100.0}:saturation={sat/100.0}"
        flip_filter = "hflip," if flip.lower() == "true" else ""
        
        # ၃။ Background Blur အတွက် Filter
        # video ကို ပထမဆုံး w, h အတိုင်း scale လုပ်ပြီး crop ပြီးမှ blur လုပ်မည်
        bg_filter = f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},boxblur=15:15"
        
        # ၄။ Foreground (Inner Crop & Zoom) အတွက် Filter တွက်ချက်ခြင်း
        fg_crop_filter = ""
        if inner_crop != "none":
            # Crop ratio များကို FFmpeg နားလည်သော ပုံစံဖြင့် ရေးသားခြင်း
            if inner_crop == "3:4": fg_crop_filter = "crop=ih*3/4:ih,"
            elif inner_crop == "16:9": fg_crop_filter = "crop=ih*16/9:ih," # 16:9 တွက်ချက်မှု ပြင်ဆင်ထားသည်
            elif inner_crop == "1:1": fg_crop_filter = "crop=min(iw\\,ih):min(iw\\,ih),"
            elif inner_crop == "4:5": fg_crop_filter = "crop=ih*4/5:ih,"
            elif inner_crop == "9:16": fg_crop_filter = "crop=ih*9/16:ih,"

        # Foreground ၏ အရွယ်အစားကို W နှင့် H အတိုင်း Scale လုပ်ပြီး Zoom ဖြင့် ထပ်မံမြှောက်သည်
        # ကိန်းပြည့်ဖြစ်စေရန် int() သုံးထားသည်
        fg_w = int(w * zoom)
        fg_h = int(h * zoom)
        
        # အရွယ်အစားကို W နှင့် H အချိုးအစားအတိုင်း အရင် Scale လုပ်ပြီးမှ Crop လုပ်သည်
        fg_filter = f"{flip_filter}{color_filter},{fg_crop_filter}scale={fg_w}:{fg_h}:force_original_aspect_ratio=decrease"
        
        # ၅။ Blur Position တွက်ချက်ခြင်း (ကိန်းပြည့်ဖြစ်ရန် int() သုံးထားသည်)
        bY = int((blur_pos / 100.0) * h)
        bH = int(blur_height)
        bTop = max(0, bY - (bH // 2))
        safe_pan = int(pan_y)

        # ၆။ FFmpeg Filter Complex အပြည့်အစုံ
        # eval=frame ကို ရှောင်ရှားရန် overlay တွက်ချက်မှုကို ပြင်ဆင်ထားသည်
        filter_complex = (
            f"[0:v]split=2[bg_src][fg_src];"
            f"[bg_src]{bg_filter}[bg];"
            f"[fg_src]{fg_filter}[fg];"
            f"[bg][fg]overlay=(W-w)/2:((H-h)/2)+({safe_pan})[merged];"
            f"[merged]split=2[m1][m2];"
            f"[m2]crop={w}:{bH}:0:{bTop},boxblur=15:5[sub_blur];"
            f"[m1][sub_blur]overlay=0:{bTop}[final]"
        )

        # Rendering Engine
        ffmpeg_cmd = [
            "ffmpeg", "-y", "-i", input_video,
            "-filter_complex", filter_complex,
            "-map", "[final]",
            "-map", "0:a?", 
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
            "-c:a", "aac",
            output_video
        ]
        
        # Error အတိအကျကို သိရှိရန် stdout ဖြင့် ဖမ်းယူမည်
        process = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
        if process.returncode != 0:
            # Error log ကို console တွင် ပြမည်
            print("FFmpeg Error Output:", process.stderr) 
            # Error နောက်ဆုံးစာကြောင်းများကိုသာ ထုတ်ပြမည်
            error_msg = process.stderr.split('\n')[-5:] 
            raise Exception(f"FFmpeg Failed: {' '.join(error_msg)}")

        return FileResponse(output_video, media_type="video/mp4", filename=f"AiMaster_Rendered_{task_id}.mp4")
    
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
    finally:
        if os.path.exists(input_video):
            os.remove(input_video)
