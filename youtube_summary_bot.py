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
    except Exception:
        return False


def get_youtube_transcript(video_url):
    """Fetch YouTube transcript"""
    try:
        video_id = video_url.split("v=")[1].split("&")[0]
        transcript = YouTubeTranscriptApi.get_transcript(video_id)
        text = " ".join([item["text"] for item in transcript])
        return text
    except (TranscriptsDisabled, NoTranscriptAvailable):
        return None


async def generate_summary(text, summary_length):
    """Generate summaries using OpenAI"""
    client = OpenAI(api_key=OPENAI_API_KEY)
    prompt_templates = {
        "short": (
            "Provide a concise summary of the following transcript. Include only the most critical information in a "
            "few sentences."
            "Ensure the summary does not exceed 200 characters."
        ),
        "medium": (
            "Provide a moderately detailed summary of the following transcript. Cover the main points and include "
            "essential context in a few paragraphs."
            "Ensure the summary does not exceed 800 characters."
        ),
        "long": (
            "Provide a detailed summary of the following transcript. Include all key points, detailed explanations, "
            "and context to give a comprehensive understanding of the content."
            "Ensure the summary does not exceed 1800 characters."
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
async def summarize(ctx, summary_type: str, video_url: str):
    if summary_type.lower() not in ["short", "medium", "long"]:
        await ctx.send("Invalid summary type. Please choose 'short', 'medium', or 'long'.")
        return

    if not is_valid_youtube_url(video_url):
        await ctx.send("Invalid YouTube URL. Please provide a valid URL.")
        return

    await ctx.send("Fetching the transcript...")

    transcript = get_youtube_transcript(video_url)
    if transcript:
        await ctx.send("Transcript fetched successfully. Generating summaries...")

        summary = await generate_summary(transcript, summary_type.lower())

        await ctx.send(f"**{summary_type.capitalize()} Summary:**\n" + summary)
    else:
        await ctx.send("Failed to fetch the transcript. It might be disabled or unavailable for this video.")


bot.run(TOKEN)
