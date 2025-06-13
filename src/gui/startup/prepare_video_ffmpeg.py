"""
Alternative video preparation script using ffmpeg directly
More reliable than moviepy for simple operations
"""
import os
import sys
import subprocess
from pathlib import Path
import tempfile
import shutil


def check_ffmpeg():
    """Check if ffmpeg is available"""
    try:
        # Try to find ffmpeg from imageio_ffmpeg
        import imageio_ffmpeg
        ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
        print(f"Found ffmpeg via imageio_ffmpeg: {ffmpeg_path}")
        return ffmpeg_path
    except ImportError:
        pass
    
    # Try system ffmpeg
    try:
        result = subprocess.run(["ffmpeg", "-version"], capture_output=True)
        if result.returncode == 0:
            print("Found system ffmpeg")
            return "ffmpeg"
    except FileNotFoundError:
        pass
    
    # Install imageio_ffmpeg if needed
    print("ffmpeg not found. Installing imageio_ffmpeg...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "imageio_ffmpeg"])
    
    import imageio_ffmpeg
    ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
    print(f"Installed and found ffmpeg: {ffmpeg_path}")
    return ffmpeg_path


def download_video(url, output_path):
    """Download video using yt-dlp"""
    try:
        import yt_dlp
    except ImportError:
        print("Installing yt-dlp...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "yt-dlp"])
        import yt_dlp
    
    ydl_opts = {
        'format': 'mp4/best[ext=mp4]',
        'outtmpl': str(output_path),
        'quiet': False,
        'no_warnings': False,
    }
    
    print(f"Downloading video from: {url}")
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])
    print("Download complete!")


def trim_video_ffmpeg(ffmpeg_path, input_path, output_path, duration=3):
    """Trim video using ffmpeg directly and remove audio"""
    print(f"Trimming video to {duration} seconds and removing audio...")
    
    # Build ffmpeg command
    # -i: input file
    # -t: duration
    # -c:v: video codec (copy means no re-encoding for speed)
    # -an: no audio
    # -y: overwrite output
    cmd = [
        ffmpeg_path,
        "-i", str(input_path),
        "-t", str(duration),
        "-c:v", "libx264",  # Re-encode to ensure compatibility
        "-preset", "fast",   # Fast encoding
        "-crf", "23",       # Good quality
        "-an",              # Remove audio
        "-y",               # Overwrite
        str(output_path)
    ]
    
    try:
        # Run ffmpeg
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"ffmpeg error: {result.stderr}")
            raise Exception("ffmpeg failed")
            
        print("Video trimmed successfully (no audio)!")
        
    except Exception as e:
        print(f"Error running ffmpeg: {e}")
        raise


def prepare_video():
    """Main function to prepare the startup video"""
    print("Startup Video Preparation (using ffmpeg directly)")
    print("=" * 50)
    
    # Check for ffmpeg
    ffmpeg_path = check_ffmpeg()
    if not ffmpeg_path:
        print("Could not find or install ffmpeg. Exiting.")
        return
    
    # Setup paths
    script_dir = Path(__file__).parent
    project_root = script_dir.parent.parent.parent
    resources_dir = project_root / "resources"
    resources_dir.mkdir(exist_ok=True)
    
    final_video_path = resources_dir / "startup_video.mp4"
    
    # Check if video already exists
    if final_video_path.exists():
        response = input(f"\nVideo already exists at {final_video_path}\nOverwrite? (y/n): ")
        if response.lower() != 'y':
            print("Keeping existing video. Exiting.")
            return
    
    # Create temporary directory for processing
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        downloaded_video = temp_path / "full_video.mp4"
        
        try:
            # Download the video
            video_url = "https://www.youtube.com/watch?v=hn6Re02LRUw"
            download_video(video_url, downloaded_video)
            
            # Trim to 3 seconds using ffmpeg
            trim_video_ffmpeg(ffmpeg_path, downloaded_video, final_video_path, duration=3)
            
            print(f"\n✅ Success! Startup video saved to:\n{final_video_path}")
            print(f"File size: {final_video_path.stat().st_size / 1024 / 1024:.2f} MB")
            
        except Exception as e:
            print(f"\n❌ Error preparing video: {e}")
            print("The application will still work using the fallback splash screen.")
            return
    
    print("\nYou can now run the application with the custom startup video!")


if __name__ == "__main__":
    prepare_video()