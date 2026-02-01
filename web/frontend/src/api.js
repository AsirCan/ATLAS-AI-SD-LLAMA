import axios from 'axios';

const API_BASE_URL = 'http://127.0.0.1:8000/api';

// Create axios instance with timeout
const client = axios.create({
    baseURL: API_BASE_URL,
    timeout: 300000, // 5 minutes (for image gen)
});

export const api = {
    // Chat with LLM
    chat: async (message) => {
        try {
            const response = await client.post('/chat', { message });
            return response.data;
        } catch (error) {
            console.error('Chat API Error:', error);
            throw error;
        }
    },

    // Generate Image
    generateImage: async (prompt) => {
        try {
            const response = await client.post('/image', { prompt });
            return response.data;
        } catch (error) {
            console.error('Image API Error:', error);
            throw error;
        }
    },

    // Text to Speech (Returns Blob)
    tts: async (text) => {
        try {
            const response = await client.post('/tts', { text }, { responseType: 'blob' });
            return response.data;
        } catch (error) {
            console.error('TTS API Error:', error);
            throw error;
        }
    },

    // Speech to Text (Uploads Audio File)
    stt: async (audioBlob) => {
        try {
            const formData = new FormData();
            // Ensure file name ends with .wav
            formData.append('file', audioBlob, 'voice_input.wav');

            const response = await client.post('/stt', formData, {
                headers: {
                    'Content-Type': 'multipart/form-data',
                },
            });
            return response.data;
        } catch (error) {
            console.error('STT API Error:', error);
            throw error;
        }
    },

    // --- News & Instagram ---
    generateNewsImage: async () => {
        try {
            const response = await client.post('/news/generate', {}, { timeout: 600000 }); // 10 min timeout
            return response.data;
        } catch (error) {
            console.error('News Gen Error:', error);
            throw error;
        }
    },

    generateNewsVideo: async () => {
        try {
            // 5 min timeout
            const response = await client.post('/news/video_generate', {}, { timeout: 300000 });
            return response.data;
        } catch (error) {
            console.error('News Video Gen Error:', error);
            throw error;
        }
    },

    checkNewsVideoProgress: async () => {
        try {
            const response = await client.get('/news/video_progress');
            return response.data;
        } catch (error) {
            return { status: "error", error: error.toString() };
        }
    },

    // Generate Carousel
    generateCarousel: async () => {
        try {
            const response = await client.post('/carousel/generate', {});
            return response.data;
        } catch (error) {
            console.error('Carousel Gen Error:', error);
            throw error;
        }
    },

    // Check Carousel Progress
    checkCarouselProgress: async () => {
        try {
            const response = await client.get('/carousel/progress');
            return response.data;
        } catch (error) {
            console.error('Carousel Progress Error:', error);
            return { progress: 0 };
        }
    },

    uploadToInstagram: async (imagePath, caption) => {
        try {
            const response = await client.post('/instagram/upload', {
                image_path: imagePath,
                caption: caption
            });
            return response.data;
        } catch (error) {
            console.error('Insta Upload Error:', error);
            throw error;
        }
    },

    // Upload Carousel
    uploadCarouselToInstagram: async (imagePaths, caption) => {
        try {
            const response = await client.post('/carousel/upload', {
                image_paths: imagePaths,
                caption: caption
            });
            return response.data;
        } catch (error) {
            console.error('Carousel Upload Error:', error);
            throw error;
        }
    },

    // --- Instagram Auth (Keyring-backed) ---
    saveInstagramCredentials: async (username, password) => {
        try {
            const response = await client.post('/instagram/credentials', { username, password });
            return response.data;
        } catch (error) {
            console.error('Instagram Credentials Error:', error);
            return { success: false, error: error.toString() };
        }
    },

    resetInstagramSession: async () => {
        try {
            const response = await client.post('/instagram/session/reset');
            return response.data;
        } catch (error) {
            console.error('Instagram Session Reset Error:', error);
            return { success: false, error: error.toString() };
        }
    },

    checkProgress: async () => {
        try {
            const response = await client.get('/progress');
            return response.data;
        } catch (error) {
            return { progress: 0 };
        }
    },

    // --- Autonomous Agent ---
    runAutonomousAgent: async (live = false) => {
        try {
            const response = await client.post('/agent/run', null, { params: { live } });
            return response.data;
        } catch (error) {
            console.error('Agent Run Error:', error);
            throw error;
        }
    },

    checkAgentProgress: async () => {
        try {
            const response = await client.get('/agent/progress');
            return response.data;
        } catch (error) {
            console.error('Agent Progress Error:', error);
            return { status: "error", error: error.toString() };
        }
    },

    cancelAgent: async () => {
        try {
            const response = await client.post('/agent/cancel');
            return response.data;
        } catch (error) {
            console.error('Agent Cancel Error:', error);
            return { success: false, error: error.toString() };
        }
    }
};
