import { useCallback, useRef, useState } from "react";

/**
 * Hook for recording audio from the microphone using the MediaRecorder API.
 * Returns a start/stop API and the recorded audio blob.
 */
export function useRecorder() {
  const [recording, setRecording] = useState(false);
  const [blob, setBlob] = useState<Blob | null>(null);
  const [error, setError] = useState<string | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  const start = useCallback(async () => {
    setError(null);
    setBlob(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      chunksRef.current = [];
      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };
      recorder.onstop = () => {
        const audioBlob = new Blob(chunksRef.current, { type: "audio/webm" });
        setBlob(audioBlob);
        stream.getTracks().forEach((t) => t.stop());
      };
      mediaRecorderRef.current = recorder;
      recorder.start();
      setRecording(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Microphone access denied");
    }
  }, []);

  const stop = useCallback(() => {
    mediaRecorderRef.current?.stop();
    setRecording(false);
  }, []);

  return { recording, blob, error, start, stop };
}
