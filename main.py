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
    return {"status": "AI Master Backend Engine V8 (Final Optimized) is Running!"}

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
    recap_text: str = Form(""), # စာသားအတွက် အသစ်
    text_pos: int = Form(90),    # စာသားနေရာ
    text_size: int = Form(40),   # စာသားအရွယ်အစား
    text_color: str = Form("#FFDE00") # စာသားအရောင်
):
    task_id = str(uuid.uuid4())[:8]
    input_video = f"temp_in_{task_id}.mp4"
    output_video = f"temp_out_{task_id}.mp4"
    # ဖောင့်ဖိုင် လိုအပ်ပါက ဆာဗာတွင်ရှိသော နေရာကို ညွှန်းရမည်။ (လောလောဆယ် default font သုံးထားသည်)

    with open(input_video, "wb") as f:
        f.write(await video.read())

    try:
        w, h = 720, 1280
        if ratio == "16:9": w, h = 1280, 720
        elif ratio == "1:1": w, h = 1080, 1080

        # ၁။ အရောင်ချိန်ခြင်း (FFmpeg Formula မှန်ကန်စေရန် ပြင်ဆင်ထားသည်)
        # Brightness: -1.0 to 1.0 (default 0), Contrast: -2.0 to 2.0 (default 1), Saturation: 0.0 to 3.0 (default 1)
        b_val = (bri - 100) / 100.0 
        c_val = max(-2.0, min(2.0, con / 100.0))
        s_val = max(0.0, min(3.0, sat / 100.0))
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
        
        fg_filter = f"{flip_filter}{color_filter},{fg_crop_filter}scale={fg_w}:{fg_h}:force_original_aspect_ratio=decrease"
        
        bY = int((blur_pos / 100.0) * h)
        bH = make_even(blur_height)
        bTop = make_even(max(0, bY - (bH // 2)))
        
        if bTop + bH > h: bH = make_even(h - bTop)
        if bH <= 0: bH = 2

        safe_pan = make_even(pan_y)

        # ၂။ စာသားထည့်ခြင်း (drawtext filter)
        # text_color က '#FFDE00' ပုံစံလာမည်ဖြစ်ရာ FFmpeg အတွက် အဆင်ပြေစေရန်
        tY = int((text_pos / 100.0) * h)
        # ယာယီစာသားအတွက် Escape characters ထည့်ခြင်း
        safe_text = recap_text.replace("'", "").replace(":", "\\:").replace("\n", " ") if recap_text else "Preview Text"
        
        # drawtext filter ကိုပေါင်းထည့်ခြင်း
        # မှတ်ချက် - ဆာဗာတွင် မြန်မာဖောင့် မရှိပါက လေးထောင့်တုံးများပေါ်နိုင်ပါသည်။ 
        # (တကယ့်အလုပ်လုပ်မည့်အခါ Subtitle File (.srt) ဖြင့် burn ရန် ပိုကောင်းပါသည်)
        text_filter = ""
        if recap_text:
            text_filter = f",drawtext=text='{safe_text}':fontcolor={text_color}:fontsize={text_size}:x=(w-text_w)/2:y={tY}:bordercolor=black:borderw=2"

        filter_complex = (
            f"[0:v]split=2[bg_src][fg_src];"
            f"[bg_src]{bg_filter}[bg];"
            f"[fg_src]{fg_filter}[fg];"
            f"[bg][fg]overlay=(W-w)/2:((H-h)/2)+({safe_pan})[merged];"
            f"[merged]split=2[m1][m2];"
            f"[m2]crop={w}:{bH}:0:{bTop},boxblur=15:5[sub_blur];"
            f"[m1][sub_blur]overlay=0:{bTop}{text_filter},format=yuv420p[final]"
        )

        # ၃။ Render မြန်အောင် Optimization များကို ထည့်သွင်းခြင်း (-threads 0, -tune fastdecode)
        ffmpeg_cmd = [
            "ffmpeg", "-y", "-i", input_video,
            "-filter_complex", filter_complex,
            "-map", "[final]",
            "-map", "0:a?", 
            "-c:v", "libx264", 
            "-preset", "ultrafast", 
            "-crf", "28",
            "-tune", "fastdecode", 
            "-threads", "0", 
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
