import { AppProvider, useAppContext } from './context/AppContext';
import InteractiveBackground from './components/InteractiveBackground';
import Sidebar from './components/Sidebar';
import GallerySidebar from './components/GallerySidebar';
import Header from './components/Header';
import ChatPage from './pages/ChatPage';
import StudioPage from './pages/StudioPage';
import VideoPage from './pages/VideoPage';

function AppLayout() {
    const {
        theme,
        appMode, setAppModeSafe,
        galleryOpen, setGalleryOpen,
        galleryImages,
        isAgentRunning,
    } = useAppContext();

    return (
        <div className="h-screen w-full dark:bg-dark-900 bg-gray-50 dark:text-white text-gray-900 font-sans selection:bg-primary/30 overflow-hidden relative flex flex-col transition-colors duration-300">

            {/* Background Layers */}
            <div className="dark:block hidden bg-living-data"></div>
            <InteractiveBackground theme={theme} />

            {/* Top Header (Full Width) */}
            <Header />

            {/* Main Layout (Sidebar + Content) */}
            <div className="flex-1 flex relative z-10 overflow-hidden">

                {/* Sidebar */}
                <Sidebar
                    currentMode={appMode}
                    setMode={setAppModeSafe}
                    isGalleryOpen={galleryOpen}
                    onOpenGallery={() => setGalleryOpen(prev => !prev)}
                    lockNavigation={isAgentRunning}
                />

                {/* Content Area */}
                <div className="flex-1 flex flex-col relative h-full overflow-hidden">
                    <main className="flex-1 flex flex-col relative z-10 p-6 md:p-10 h-full">
                        {appMode === 'studio' ? (
                            <StudioPage />
                        ) : appMode === 'video' ? (
                            <VideoPage />
                        ) : (
                            <ChatPage />
                        )}
                    </main>
                </div>

                {/* Gallery Sidebar */}
                <GallerySidebar
                    isOpen={galleryOpen}
                    onClose={() => setGalleryOpen(false)}
                    images={galleryImages}
                />
            </div>
        </div>
    );
}

function App() {
    return (
        <AppProvider>
            <AppLayout />
        </AppProvider>
    );
}

export default App;
