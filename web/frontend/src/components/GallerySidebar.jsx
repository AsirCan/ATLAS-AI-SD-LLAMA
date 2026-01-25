import React from 'react';
import { X, Download, ExternalLink, Image as ImageIcon } from 'lucide-react';

const GallerySidebar = ({ isOpen, onClose, images }) => {
    return (
        <div
            className={`fixed top-0 right-0 h-full w-80 dark:bg-dark-900/95 bg-white/95 backdrop-blur-xl dark:border-l border-l border-white/10 border-gray-200 z-50 transform transition-transform duration-300 ease-in-out shadow-2xl ${isOpen ? 'translate-x-0' : 'translate-x-full'
                }`}
        >
            <div className="p-4 dark:border-b border-b border-white/10 border-gray-200 flex items-center justify-between">
                <h2 className="text-xl font-bold flex items-center gap-2 dark:text-white text-gray-800">
                    <ImageIcon className="text-accent" size={20} />
                    Galeri
                </h2>
                <button
                    onClick={onClose}
                    className="p-2 dark:hover:bg-white/10 hover:bg-gray-100 rounded-lg transition-colors dark:text-gray-400 text-gray-600"
                >
                    <X size={20} />
                </button>
            </div>

            <div className="p-4 overflow-y-auto h-[calc(100%-64px)] space-y-4">
                {images.length === 0 ? (
                    <div className="text-center text-gray-500 py-10">
                        <ImageIcon size={48} className="mx-auto mb-4 opacity-20" />
                        <p>Henüz görsel oluşturulmadı.</p>
                    </div>
                ) : (
                    images.map((img, idx) => (
                        <div key={idx} className="group relative rounded-xl overflow-hidden dark:border border border-white/10 border-gray-200 dark:bg-white/5 bg-gray-50 shadow-sm">
                            <img
                                src={img.url}
                                alt={img.prompt}
                                className="w-full h-40 object-cover transition-transform group-hover:scale-105"
                            />
                            <div className="absolute inset-0 bg-black/60 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center gap-3">
                                <a
                                    href={img.url}
                                    download={`atlas_gen_${idx}.png`}
                                    className="p-2 bg-white/10 rounded-full hover:bg-white/20 text-white transition-colors"
                                    title="İndir"
                                >
                                    <Download size={18} />
                                </a>
                                <a
                                    href={img.url}
                                    target="_blank"
                                    rel="noreferrer"
                                    className="p-2 bg-white/10 rounded-full hover:bg-white/20 text-white transition-colors"
                                    title="Tam Boyut"
                                >
                                    <ExternalLink size={18} />
                                </a>
                            </div>
                            <div className="p-2 text-xs dark:text-gray-400 text-gray-600 truncate dark:border-t border-t border-white/5 border-gray-200 dark:bg-dark-800 bg-white">
                                {img.prompt}
                            </div>
                        </div>
                    ))
                )}
            </div>
        </div>
    );
};

export default GallerySidebar;
