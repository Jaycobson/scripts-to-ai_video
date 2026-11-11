import io
import os
import time
import zipfile
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from pipeline.backends import ComfyUIBackend, OpenAIBackend
from pipeline.runner import run_pipeline
from pipeline.video import ffmpeg_available

load_dotenv()
st.set_page_config(page_title="Script to Visuals", page_icon="🎬", layout="wide")

st.markdown("""
<style>
.block-container {max-width: 1150px; padding-top: 2rem;}
.hero {padding: 2.2rem 2.4rem; border-radius: 18px; color: #fff; margin-bottom: 1.5rem;
       background: linear-gradient(120deg, #0a2f7a 0%, #1f5fd8 55%, #ffc61a 100%);
       box-shadow: 0 6px 20px rgba(10, 47, 122, .25);}
.hero h1 {color: #ffffff; margin: 0 0 .3rem 0; font-size: 2.3rem;}
.hero p {color: #e6efff; margin: 0 0 1rem 0; font-size: 1.05rem; max-width: 65%;}
.chip {display: inline-block; padding: .25rem .8rem; margin: 0 .4rem .3rem 0; border-radius: 999px;
       background: rgba(255,255,255,.18); font-size: .85rem;}
.stButton > button {height: 3rem; font-weight: 600; border-radius: 10px;
       background: #ffc61a; color: #0a2f7a; border: none;}
.stButton > button:hover {background: #ffd54d; color: #0a2f7a;}
</style>
<div class="hero">
  <h1>🎬 Script to Visuals</h1>
  <p>Turn a written script into consistent illustrated scenes with a narrated video, in one click.</p>
</div>
""", unsafe_allow_html=True)

EXAMPLE = ("Scene 1: On a bright Saturday morning in Lagos, Ife skips along the sunny path towards the community playground, holding her water bottle.\n\n"
           "Scene 2: At the gate, Chidi waves excitedly, and Aunty Bisi reminds the children to stay together and look out for one another.\n\n"
           "Scene 3: Ife and Chidi take turns on the colourful slide, laughing and waiting patiently for each person to finish.\n\n"
           "Scene 4: Under a big green tree, Aunty Bisi hands out sun hats, and Ife and Chidi put them on before they play.\n\n"
           "Scene 5: Chidi spots a tall swing set, and Ife shows him how to hold the ropes tightly and swing gently.\n\n"
           "Scene 6: Ife and Chidi share a football with the other children, passing it kindly on the open grass.\n\n"
           "Scene 7: When the afternoon sun grows hot, Ife and Chidi rest in the shade, drinking cold water and sharing fruit.\n\n"
           "Scene 8: As the day ends, Ife and Chidi tidy up the toys, wave goodbye to Aunty Bisi, and walk home smiling in the golden light.")
CHARS = ("Ife: 8-year-old Nigerian girl, two puffy afro puffs with yellow ribbons, bright orange dress, white sandals\n"
         "Chidi: 9-year-old Nigerian boy, short black hair, blue t-shirt, khaki shorts, red sneakers\n"
         "Bisi: Nigerian woman in her 40s, purple and gold headwrap, long green ankara dress, warm smile")

left, right = st.columns([3, 2], gap="large")
with left:
    script = st.text_area("📝 Script", EXAMPLE, height=330,
                          help="Start scenes with 'Scene 1:' or separate them with a blank line. The text is also the narration.")
with right:
    chars_text = st.text_area("🧑🏾‍🤝‍🧑🏾 Characters (Name: description)", CHARS, height=180,
                              help="These descriptions are added to every prompt so characters look the same in each scene.")
    style = st.text_input("Visual style", "bright, cheerful children's picture-book illustration, vibrant saturated colours, soft sunlight, flat shapes with gentle shading, friendly characters with big expressive eyes, clean uncluttered backgrounds")

# engine = st.radio("Image engine", ["OpenAI", "ComfyUI (local)"], horizontal=True)
engine = 'OpenAI'
if engine.startswith("ComfyUI"):
    with st.expander("ComfyUI settings", expanded=True):
        c1, c2 = st.columns(2)
        url = c1.text_input("Server URL", os.getenv("COMFYUI_URL", "http://127.0.0.1:8188"))
        ckpt = c2.text_input("Checkpoint", os.getenv("COMFYUI_CHECKPOINT", "sd_xl_base_1.0.safetensors"))

if st.button("✨ Generate video", type="primary", use_container_width=True):
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        st.error("OPENAI_API_KEY not found. Add it to your .env file (needed for narration too).")
    elif not ffmpeg_available():
        st.error("FFmpeg was not found on this machine. Install it and make sure it is on your PATH.")
    else:
        started = time.time()
        try:
            backend = OpenAIBackend(api_key) if engine == "OpenAI" else ComfyUIBackend(url, ckpt)
            out_dir = Path("outputs") / time.strftime("%Y%m%d_%H%M%S")
            weights = {"images": (0.0, 0.6, "Generating scene images"),
                       "narration": (0.6, 0.2, "Recording narration"),
                       "video": (0.8, 0.2, "Assembling video")}
            with st.status("Building your video...", expanded=True) as status:
                bar = st.progress(0.0)

                def on_progress(stage, done, total):
                    start, span, label = weights[stage]
                    bar.progress(min(start + span * done / total, 1.0), text=f"{label} ({done}/{total})")

                result = run_pipeline(script, chars_text, style, backend, out_dir,
                                      api_key=api_key, on_progress=on_progress)
                status.update(label="Done", state="complete", expanded=False)
            result["seconds"] = time.time() - started
            st.session_state["out"] = result
        except Exception as e:
            st.error(f"Generation failed: {e}")

out = st.session_state.get("out")
if out:
    st.divider()
    m1, m2, m3 = st.columns(3)
    m1.metric("Scenes", len(out["scenes"]))
    m2.metric("Generated in", f"{out['seconds']:.0f}s")
    m3.metric("Format", "320*240 · MP4")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for f in Path(out["dir"]).iterdir():
            z.write(f, f.name)

    tab_video, tab_scenes = st.tabs(["🎬 Video", "🖼️ Scenes"])
    with tab_video:
        st.video(out["video"])
        d1, d2 = st.columns(2)
        d1.download_button("⬇️ Download video (MP4)", Path(out["video"]).read_bytes(),
                           "script2visuals.mp4", "video/mp4", use_container_width=True)
        d2.download_button("📦 Download everything (ZIP)", buf.getvalue(),
                           "script2visuals_package.zip", "application/zip", use_container_width=True)
    with tab_scenes:
        cols = st.columns(2, gap="large")
        for i, s in enumerate(out["scenes"]):
            with cols[i % 2].container(border=True):
                st.markdown(f"**Scene {s['index']}**")
                st.image(s["image"], use_container_width=True)
                st.caption(s["text"])
                st.audio(s["audio"])
                with st.expander("Prompt used"):
                    st.code(s["prompt"], language=None)
