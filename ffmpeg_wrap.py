# ffmpeg_wrap.py
import os, shutil, subprocess, tempfile
import cv2

class LosslessWriter:
    """
    If ffmpeg is available, write PNG frames to a temp dir and assemble the final video with the chosen codec.
    Supported codecs:
      - 'ffv1'      (very large but robust)
      - 'h264rgb'   (lossless, much smaller; requires libx264rgb)
    Fallback: write AVI via OpenCV (may be MJPEG).
     """
    def __init__(self, out_path, width, height, fps, codec="ffv1", audio_src=None):
        self.out_path = out_path
        self.audio_src = audio_src  # optional file whose audio track is muxed into the output
        self.width, self.height, self.fps = width, height, fps
        self.codec = codec.lower()
        self.have_ffmpeg = shutil.which("ffmpeg") is not None
        self.tmpdir = None
        self.writer = None
        self.count = 0
        if self.have_ffmpeg:
            self.tmpdir = tempfile.mkdtemp(prefix="stego_png_")
            # For libx264rgb, MP4 is often incompatible with rgb24. Prefer MKV.
            if self.codec == "h264rgb" and not self.out_path.lower().endswith((".mkv", ".mka", ".mks")):
                root, _ext = os.path.splitext(self.out_path)
                self.out_path = root + ".mkv"
        else:
            fourcc = 0
            self.writer = cv2.VideoWriter(out_path, fourcc, fps, (width, height))
            if not self.writer.isOpened():
                fourcc = cv2.VideoWriter_fourcc(*'MJPG')
                self.writer = cv2.VideoWriter(out_path, fourcc, fps, (width, height))
                if not self.writer.isOpened():
                    raise RuntimeError("Cannot open VideoWriter; install ffmpeg and use FFV1 mode.")

    def write_frames(self, stacked_bgr):
        # stacked_bgr: (N,H,W,3)
        if self.have_ffmpeg:
            for i in range(stacked_bgr.shape[0]):
                fn = os.path.join(self.tmpdir, f"frame_{self.count:06d}.png")
                cv2.imwrite(fn, stacked_bgr[i])
                self.count += 1
        else:
            for i in range(stacked_bgr.shape[0]):
                self.writer.write(stacked_bgr[i])
                self.count += 1

    def close(self):
        if self.have_ffmpeg:
            # assemble via ffmpeg using selected codec
            input_pat = os.path.join(self.tmpdir, "frame_%06d.png")
            if self.codec == "h264rgb":
                # Strictly lossless RGB H.264 in MKV. Keyframes only (-g 1).
                vargs = ["-c:v", "libx264rgb", "-crf", "0", "-preset", "veryslow",
                         "-pix_fmt", "rgb24", "-g", "1"]
            else:
                # FFV1 lossless (very robust). Keep rgb24, CRC slices, keyframes only.
                # MKV is ideal; ffmpeg will pick from extension.
                vargs = ["-c:v", "ffv1", "-level", "3", "-pix_fmt", "rgb24", "-g", "1", "-slicecrc", "1"]
            base = ["ffmpeg", "-y", "-framerate", str(self.fps), "-i", input_pat]
            video_only = base + vargs + [self.out_path]
            attempts = []
            if self.audio_src:
                # Audio is never touched by the stego bits, so copy it as-is when the container
                # accepts the codec; otherwise let ffmpeg re-encode to the container default.
                # "1:a?" makes the audio map optional, so sources without audio still work.
                with_audio = base + ["-i", self.audio_src, "-map", "0:v:0", "-map", "1:a?"] + vargs
                attempts.append(with_audio + ["-c:a", "copy", self.out_path])
                attempts.append(with_audio + [self.out_path])
            attempts.append(video_only)
            try:
                for i, cmd in enumerate(attempts):
                    try:
                        subprocess.run(cmd, check=True)
                        break
                    except subprocess.CalledProcessError:
                        if i == len(attempts) - 1:
                            raise
                        if cmd is attempts[-2]:
                            print("[warn] Could not add the source audio to the output; writing video only.")
            except subprocess.CalledProcessError as e:
                raise RuntimeError(
                    "ffmpeg failed while assembling the video.\n"
                    f"Command: {' '.join(cmd)}\n"
                    f"Exit code: {e.returncode}\n"
                    "Hints:\n"
                    "  • Ensure ffmpeg supports libx264rgb (for h264rgb) or ffv1 codec.\n"
                    "  • For h264rgb, use a .mkv output (RGB in .mp4 is often unsupported).\n"
                ) from e
            finally:
                shutil.rmtree(self.tmpdir, ignore_errors=True)
        else:
            self.writer.release()
