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
    return {"status": "AI Master Backend Engine V8 (Final Fast Render) is Running!"}

def make_even(n):
    return max(2, int(n) // 2 * 2)

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
    sat: int = Form(100),
    # UI မှ စာသား၊ နေရာနှင့် အရွယ်အစားများကို လက်ခံရန် (index.html တွင် ထပ်မံဖြည့်စွက်ရန်လိုမည်)
    recap_text: str = Form(""),
    text_pos: int = Form(90),
    text_size: int = Form(40),
    text_color: str = Form("#FFDE00")
):
    task_id = str(uuid.uuid4())[:8]
    input_video = f"temp_in_{task_id}.mp4"
    output_video = f"temp_out_{task_id}.mp4"

    with open(input_video, "wb") as f:
        f.write(await video.read())

    try:
        # Render မြန်စေရန် Output Resolution ကို အနည်းငယ် လျှော့ချထားသည် (540x960 ဖြင့် စမ်းသပ်ကြည့်ပါ)
        # အကယ်၍ ကြည်လင်ပြတ်သားမှု လိုအပ်ပါက 720x1280 သို့ ပြန်ပြောင်းနိုင်သည်
        w, h = 540, 960 
        if ratio == "16:9": w, h = 960, 540
        elif ratio == "1:1": w, h = 720, 720

        # အရောင်ပြောင်းခြင်းကို သေချာစေရန် (brightness သည် -1.0 မှ 1.0, contrast သည် -2.0 မှ 2.0 အစရှိသဖြင့်)
        b_val = (bri - 100) / 100.0  # 0.0 သည် ပုံမှန်
        c_val = con / 100.0          # 1.0 သည် ပုံမှန်
        s_val = sat / 100.0          # 1.0 သည် ပုံမှန်
        color_filter = f"eq=brightness={b_val}:contrast={c_val}:saturation={s_val}"
        
        flip_filter = "hflip," if flip.lower() == "true" else ""
        
        bg_filter = f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},boxblur=15:15"
        
        fg_crop_filter = ""
        if inner_crop != "none":
            r_val = 1.0
            if inner_crop == "3:4": r_val = 3.0/4.0
            elif inner_crop == "16:9": r_val = 16.0/9.0
            elif inner_crop == "1:1": r_val = 1.0
            elif inner_crop == "4:5": r_val = 4.0/5.0
            elif inner_crop == "9:16": r_val = 9.0/16.0
            
            fg_crop_filter = f"crop='floor(min(iw,ih*{r_val})/2)*2':'floor(min(ih,iw/{r_val})/2)*2',"

        fg_w = make_even(w * zoom)
        fg_h = make_even(h * zoom)
        
        # Foreground ကို Color Filter ထည့်သွင်းခြင်း
        fg_filter = f"{flip_filter}{color_filter},{fg_crop_filter}scale={fg_w}:{fg_h}:force_original_aspect_ratio=decrease"
        
        bY = int((blur_pos / 100.0) * h)
        bH = make_even(blur_height)
        bTop = make_even(max(0, bY - (bH // 2)))
        
        if bTop + bH > h:
            bH = make_even(h - bTop)
        if bH <= 0:
            bH = 2

        safe_pan = make_even(pan_y)

        # စာသား (Subtitle) ရေးသားရန် (drawtext filter အသုံးပြုသည်)
        # Font ဖိုင်မရှိပါက default font ကိုသာ သုံးမည်
        tY = int((text_pos / 100.0) * h)
        text_filter = ""
        if recap_text:
             # FFmpeg drawtext တွင် အသုံးပြုရန် escape လုပ်ခြင်း
             safe_text = recap_text.replace("'", "\\'").replace(":", "\\:")
             t_color = text_color.replace("#", "0x")
             # drawtext ဖြင့် စာသားထည့်ခြင်း
             text_filter = f",drawtext=text='{safe_text}':fontcolor={t_color}:fontsize={text_size}:x=(w-text_w)/2:y={tY}:borderw=2:bordercolor=black"

        filter_complex = (
            f"[0:v]split=2[bg_src][fg_src];"
            f"[bg_src]{bg_filter}[bg];"
            f"[fg_src]{fg_filter}[fg];"
            f"[bg][fg]overlay=(W-w)/2:((H-h)/2)+({safe_pan})[merged];"
            f"[merged]split=2[m1][m2];"
            f"[m2]crop={w}:{bH}:0:{bTop},boxblur=15:5[sub_blur];"
            f"[m1][sub_blur]overlay=0:{bTop}{text_filter},format=yuv420p[final]"
        )

        ffmpeg_cmd = [
            "ffmpeg", "-y", "-i", input_video,
            "-filter_complex", filter_complex,
            "-map", "[final]",
            "-map", "0:a?", 
            "-c:v", "libx264", 
            "-preset", "ultrafast", # အမြန်ဆုံး Render လုပ်ရန်
            "-crf", "30", # File size သေးအောင် ချိန်ညှိခြင်း (မြန်စေရန်)
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
