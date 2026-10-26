import asyncio
import edge_tts
import time
from pygame import mixer
from io import BytesIO
import threading


class EdgeTTSPlayer:
    def __init__(self, voice="zh-CN-XiaoxiaoNeural", rate="+0%", volume="+0%"):
        self.voice = voice
        self.rate = rate
        self.volume = volume
        # 初始化pygame混音器
        mixer.init()
        # 创建独立的异步事件循环和线程（用于处理语音合成）
        self.loop = asyncio.new_event_loop()
        self.closed = threading.Event()
        self.audio_thread = threading.Thread(target=self._run_audio_loop, daemon=True)
        self.audio_thread.start()

    def _run_audio_loop(self):
        """在独立线程中运行异步事件循环"""
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    async def _synthesize(self, text):
        """生成语音并返回音频流（异步方法）"""
        communicate = edge_tts.Communicate(
            text=text,
            voice=self.voice,
            rate=self.rate,
            volume=self.volume
        )

        # 创建内存缓冲区
        audio_stream = BytesIO()

        # 将音频数据写入内存缓冲区
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_stream.write(chunk["data"])

        # 重置缓冲区指针到开始位置
        audio_stream.seek(0)
        return audio_stream

    def _play_audio(self, audio_stream):
        """使用pygame播放内存中的音频流（同步方法，在主线程执行）"""
        try:
            # 直接从内存缓冲区加载音频
            mixer.music.load(audio_stream)
            # 播放音频
            mixer.music.play()

            # 等待音频播放完成（非阻塞检测）
            while mixer.music.get_busy():
                time.sleep(0.1)

            # 释放资源
            mixer.music.unload()
            print("播放完成")
        except Exception as e:
            print(f"播放音频时出错: {e}")

    async def _async_speak(self, text):
        """异步版本的语音合成+播放"""
        if not text.strip():
            print("文本为空，无法朗读。")
            return

        print(f"正在生成语音...")
        audio_stream = await self._synthesize(text)
        print(f"正在播放语音...")
        # 回到主线程播放音频（pygame可能对多线程敏感）
        self._play_audio(audio_stream)

    def speak(self, text):
        """对外接口：将文本转换为语音并播放（非阻塞）"""
        if self.closed.is_set():
            return None
        # 将语音合成任务提交到异步事件循环
        asyncio.run_coroutine_threadsafe(
            self._async_speak(text),
            self.loop
        )

    async def list_voices(self, locale_filter=None):
        """列出可用的语音"""
        voices = await edge_tts.list_voices()
        for voice in voices:
            if locale_filter is None or voice["Locale"].startswith(locale_filter):
                locale_name = voice.get('LocaleName', '未知语言名')
                print(f"{voice['ShortName']} ({voice['Gender']}) - {locale_name}")

    def save_to_file(self, text, filename="output.mp3"):
        """将文本转换为语音并保存到文件"""

        async def _save_file():
            communicate = edge_tts.Communicate(
                text=text,
                voice=self.voice,
                rate=self.rate,
                volume=self.volume
            )
            await communicate.save(filename)

        # 使用独立的事件循环执行保存操作
        save_loop = asyncio.new_event_loop()
        save_loop.run_until_complete(_save_file())
        save_loop.close()
        print(f"语音已保存为 {filename}")

    def close(self):
        """资源清理"""
        if self.closed.is_set():
            return
        self.closed.set()
        # 停止事件循环
        self.loop.call_soon_threadsafe(self.loop.stop)
        self.audio_thread.join(timeout=1.0)
        if not self.loop.is_running():
            self.loop.close()
        # 关闭pygame混音器
        mixer.quit()


if __name__ == "__main__":
    # 确保安装必要库: pip install pygame edge-tts
    tts = EdgeTTSPlayer()

    try:
        # 示例1：非阻塞播放
        tts.speak("一 二 三 四 五。")
        print("这句话会在语音播放的同时显示（非阻塞）")

        # 等待第一个语音播放完成
        time.sleep(3)

        # 示例2：连续播放
        tts.speak("这是第二句测试语音，应该在前一句完成后播放")

        # 示例3：保存到文件
        tts.save_to_file("这是保存到文件的测试语音", "test_output.mp3")

        # 等待所有操作完成
        time.sleep(5)
    finally:
        tts.close()
