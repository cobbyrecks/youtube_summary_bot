import os
import discord

from dotenv import load_dotenv
from discord.ext import commands
from openai import OpenAI
from urllib.parse import urlparse, parse_qs
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptAvailable


# Load environmental variables
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
API_KEY = os.getenv("API_KEY")
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

intents = discord.Intents.default()
intents.messages = True
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)


def is_valid_youtube_url(url):
    """Check if the url is valid"""
    try:
        parsed_url = urlparse(url)
        if parsed_url.netloc not in ["www.youtube.com", "youtube.com", "youtu.be"]:
            return False
        if "v" in parse_qs(parsed_url.query) or parsed_url.netloc == "youtu.be":
            return True
        return False
    except ValueError:
        return False


def get_youtube_transcript(video_url):
    """Fetch YouTube transcript"""
    try:
        video_id = video_url.split("v=")[1].split("&")[0]
        transcript = YouTubeTranscriptApi.get_transcript(video_id)
        return transcript
    except (TranscriptsDisabled, NoTranscriptAvailable):
        return None


def format_transcript_with_timestamps(transcript):
    """Format transcript into timestamped segments."""
    formatted_transcript = []
    for item in transcript:
        start_time = int(item["start"])
        end_time = start_time + int(item["duration"])
        start_formatted = f"{start_time // 60:02}:{start_time % 60:02}"
        end_formatted = f"{end_time // 60:02}:{end_time % 60:02}"
        formatted_transcript.append(f"{start_formatted} - {end_formatted} : \"{item['text']}\"")
    return "\n".join(formatted_transcript)


async def send_long_message(ctx, content):
    """Sends long messages in chunks of 2000 characters; limitation in discord!"""
    max_length = 2000
    if len(content) <= max_length:
        await ctx.send(content)
    else:
        for i in range(0, len(content), max_length):
            await ctx.send(content[i:i + max_length])


async def generate_summary(text, summary_length):
    """Generate summaries using OpenAI"""
    client = OpenAI(api_key=OPENAI_API_KEY)
    prompt_templates = {
        "short": (
            "Provide a concise summary of the following transcript. Focus on the most critical points, "
            "omitting unnecessary details. Format the output as follows:\n\n"
            "[START TIME] - [END TIME]: <<brief summary of the key point(s) here>>\n"
            "[START TIME] - [END TIME]: <<brief summary of the key point(s) here>>\n"
        ),
        "medium": (
            "Provide a moderately detailed summary of the following transcript. Cover the main points, key insights, "
            "and provide essential context. Format the output as follows:\n\n"
            "[START TIME] - [END TIME]: <<summary with important context here>>\n"
            "[START TIME] - [END TIME]: <<summary with important context here>>\n"
        ),
        "long": (
            "Provide a detailed and comprehensive summary of the following transcript. Include all key points, "
            "contextual explanations, and relevant details. Format the output as follows:\n\n"
            "[START TIME] - [END TIME]: <<detailed summary with context and explanation here>>\n"
            "[START TIME] - [END TIME]: <<detailed summary with context and explanation here>>\n"
        )
    }

    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {
            "role": "user",
            "content": (
                f"{prompt_templates[summary_length]}\n\n{text}"
            )
        }
    ]
    try:
        completion = client.chat.completions.create(
            model="gpt-4o",
            messages=messages
        )
        return completion.choices[0].message.content
    except Exception as error:
        return f"Error generating summary: {error}"


@bot.event
async def on_ready():
    print(f"{bot.user.name} has connected to Discord!")


@bot.command(name="summarize", help="Summarizes a YouTube video transcript. Usage: !summarize <YouTube URL>")
async def summarize(ctx, summary_type: str = None, video_url: str = None):
    if not summary_type or not video_url:
        await ctx.send("Missing arguments! Usage: `!summarize <summary_length> <YouTube URL>`")
        return

    if summary_type.lower() not in ["short", "medium", "long"]:
        await ctx.send("Invalid summary type. Please choose 'short', 'medium', or 'long'.")
        return

    if not is_valid_youtube_url(video_url):
        await ctx.send("Invalid YouTube URL. Please provide a valid URL.")
        return

    await ctx.send("Fetching the transcript...")
    transcript = get_youtube_transcript(video_url)

    if transcript:
        await ctx.send("Transcript fetched successfully. Generating summary...")
        formatted_timestamps = format_transcript_with_timestamps(transcript)
        summary = await generate_summary(formatted_timestamps, summary_type.lower())
        summary_message = f"**{summary_type.capitalize()} Summary:**\n{summary}"
        await send_long_message(ctx, summary_message)
    else:
        await ctx.send("Failed to fetch the transcript. It might be disabled or unavailable for this video.")


bot.run(TOKEN)
