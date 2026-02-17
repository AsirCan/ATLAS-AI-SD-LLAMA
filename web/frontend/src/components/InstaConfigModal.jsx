import { X, ShieldCheck, KeyRound, Globe, Link2, CheckCircle2, ExternalLink, Copy } from 'lucide-react';
import { useAppContext } from '../context/AppContext';
import { api } from '../api';

export default function InstaConfigModal() {
    const {
        showInstaLogin, instaAuthTab, setInstaAuthTab,
        graphStatus, graphTokenStatus, tokenStatusText,
        graphConfig, setGraphConfig, saveGraphConfig,
        refreshGraphStatus, refreshGraphTokenStatus, refreshImgBBConfig,
        imgbbApiKey, setImgbbApiKey, imgbbConfigured, saveImgBBConfig,
        graphEnvTemplate, copyGraphEnvTemplate, envCopied,
        closeInstaModal, instaUser, setInstaUser, instaPass, setInstaPass,
    } = useAppContext();

    if (!showInstaLogin) return null;

    return (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-[80] flex items-center justify-center p-3 animate-fade-in">
            <div className="bg-white dark:bg-dark-800 border border-gray-200 dark:border-white/10 rounded-3xl p-5 w-full max-w-xl shadow-2xl scale-in max-h-[82vh] overflow-y-auto">
                <div className="flex justify-between items-start mb-5">
                    <div>
                        <h3 className="text-xl font-bold text-gray-900 dark:text-white">Instagram Baglanti Merkezi</h3>
                        <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">Graph API onerilir, Legacy login yedek olarak durur.</p>
                    </div>
                    <button onClick={closeInstaModal} className="text-gray-400 hover:text-gray-900 dark:hover:text-white">
                        <X size={24} />
                    </button>
                </div>

                {/* Tab Buttons */}
                <div className="flex gap-2 mb-5">
                    <button
                        onClick={() => setInstaAuthTab('graph')}
                        className={`flex-1 py-2.5 rounded-xl text-sm font-semibold border transition ${instaAuthTab === 'graph'
                            ? 'bg-blue-600 text-white border-blue-500'
                            : 'bg-gray-100 dark:bg-dark-900 text-gray-700 dark:text-gray-300 border-gray-200 dark:border-white/10 hover:bg-gray-200 dark:hover:bg-dark-700'
                            }`}
                    >
                        <span className="inline-flex items-center gap-2"><ShieldCheck size={16} /> Graph API</span>
                    </button>
                    <button
                        onClick={() => setInstaAuthTab('legacy')}
                        className={`flex-1 py-2.5 rounded-xl text-sm font-semibold border transition ${instaAuthTab === 'legacy'
                            ? 'bg-emerald-600 text-white border-emerald-500'
                            : 'bg-gray-100 dark:bg-dark-900 text-gray-700 dark:text-gray-300 border-gray-200 dark:border-white/10 hover:bg-gray-200 dark:hover:bg-dark-700'
                            }`}
                    >
                        <span className="inline-flex items-center gap-2"><KeyRound size={16} /> Legacy Login</span>
                    </button>
                </div>

                {/* Graph Tab */}
                {instaAuthTab === 'graph' && (
                    <div className="space-y-4 text-left">
                        {/* Quick flow */}
                        <div className="rounded-2xl border border-indigo-200 dark:border-indigo-500/30 bg-indigo-50 dark:bg-indigo-500/10 p-4">
                            <p className="font-semibold text-indigo-700 dark:text-indigo-300">Hızlı Kullanım Akışı</p>
                            <div className="mt-2 space-y-1 text-xs text-indigo-900 dark:text-indigo-100">
                                <p><b>1)</b> Bu pencereden Graph alanlarini doldur ve <b>UI'dan .env Kaydet</b> de.</p>
                                <p><b>2)</b> Cloudflare tuneli ulasilamazsa diye <b>ImgBB Fallback</b> alanina API key gir.</p>
                                <p><b>3)</b> Studio ekraninda icerik uret ve <b>Instagram'a Yukle</b> butonuna bas.</p>
                                <p><b>4)</b> Hata olursa once <b>Durumu Yenile</b> ile durumlari kontrol et.</p>
                            </div>
                        </div>

                        {/* Status rows */}
                        <div className="rounded-xl border border-gray-200 dark:border-white/10 px-4 py-3 bg-white/60 dark:bg-dark-900/60 flex items-center justify-between">
                            <span className="text-sm text-gray-700 dark:text-gray-300">Kurulum durumu</span>
                            <span className={`text-xs font-bold px-2 py-1 rounded-md ${graphStatus.graph_ready ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/20 dark:text-emerald-300' : 'bg-amber-100 text-amber-700 dark:bg-amber-500/20 dark:text-amber-300'}`}>
                                {graphStatus.graph_ready ? 'Hazir' : `${graphStatus.filled_count}/${graphStatus.required_count} alan dolu`}
                            </span>
                        </div>

                        <div className="rounded-xl border border-gray-200 dark:border-white/10 px-4 py-3 bg-white/60 dark:bg-dark-900/60 flex items-center justify-between gap-3">
                            <div className="text-sm text-gray-700 dark:text-gray-300">
                                <div>Token durumu</div>
                                <div className="text-xs text-gray-500 dark:text-gray-400 mt-1">{tokenStatusText()}</div>
                            </div>
                            <span className={`text-xs font-bold px-2 py-1 rounded-md ${!graphTokenStatus.configured
                                ? 'bg-gray-100 text-gray-600 dark:bg-gray-700/50 dark:text-gray-300'
                                : (graphTokenStatus.needs_refresh
                                    ? 'bg-amber-100 text-amber-700 dark:bg-amber-500/20 dark:text-amber-300'
                                    : 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/20 dark:text-emerald-300')
                                }`}>
                                {!graphTokenStatus.configured ? 'Bilinmiyor' : (graphTokenStatus.needs_refresh ? 'Yenile' : 'Saglam')}
                            </span>
                        </div>

                        {/* Detailed instructions */}
                        <div className="rounded-2xl border border-gray-200 dark:border-white/10 bg-gray-50 dark:bg-dark-900 p-4">
                            <p className="font-semibold text-gray-900 dark:text-white mb-2">Graph API Bilgilerini Alma ve Alana Yerleştirme (Detaylı)</p>
                            <div className="space-y-2 text-xs text-gray-700 dark:text-gray-300">
                                <p><b>0)</b> Graph API Explorer ekranında <b>User Token</b> seçin ve şu izinleri ekleyin: <b>pages_show_list</b>, <b>pages_read_engagement</b>, <b>instagram_basic</b>, <b>instagram_content_publish</b>.</p>
                                <p><b>1)</b> Graph API Explorer'ın sağ panelindeki token değerini kopyalayıp <b>FB_ACCESS_TOKEN</b> alanına yapıştırın.</p>
                                <p><b>2)</b> Endpoint alanına <code className="px-1 py-0.5 rounded bg-black/10 dark:bg-white/10">/me/accounts?fields=id,name</code> yazıp <b>Submit</b> edin. Dönen listede kullanacağınız Facebook sayfasının <b>id</b> değerini alıp <b>FB_PAGE_ID</b> alanına girin.</p>
                                <p><b>3)</b> Endpoint alanına <code className="px-1 py-0.5 rounded bg-black/10 dark:bg-white/10">{`/{FB_PAGE_ID}?fields=instagram_business_account`}</code> yazıp <b>Submit</b> edin. Sonuçtaki <b>instagram_business_account.id</b> değerini alıp <b>IG_USER_ID</b> alanına girin.</p>
                                <p><b>4)</b> <b>Meta Developers {'>'} App settings {'>'} Basic</b> ekranından: <b>App ID</b> değerini <b>FB_APP_ID</b> alanına, <b>App Secret (Show)</b> değerini <b>FB_APP_SECRET</b> alanına girin.</p>
                                <p><b>5)</b> <code className="px-1 py-0.5 rounded bg-black/10 dark:bg-white/10">python run.py</code> komutunu çalıştırın. Tünel başlatıldığında <b>PUBLIC_BASE_URL</b> alanı otomatik doldurulur. Otomatik dolmazsa <code className="px-1 py-0.5 rounded bg-black/10 dark:bg-white/10">https://*.trycloudflare.com</code> formatındaki adresi manuel olarak girin.</p>
                                <p><b>6)</b> Tüm alanları kaydedip <b>Durumu Yenile</b> butonuna basın. Kurulum ve token göstergelerinin yeşil olması gerekir.</p>
                            </div>
                        </div>

                        {/* Recommended setup */}
                        <div className="rounded-2xl border border-blue-200 dark:border-blue-500/30 bg-blue-50 dark:bg-blue-500/10 p-4">
                            <p className="font-semibold text-blue-700 dark:text-blue-300">Onerilen kurulum (stabil)</p>
                            <ul className="mt-2 space-y-2 text-sm text-blue-800 dark:text-blue-200">
                                <li className="flex items-start gap-2"><CheckCircle2 size={16} className="mt-0.5 shrink-0" /> Meta App + Business + Page + IG baglantisini kur.</li>
                                <li className="flex items-start gap-2"><CheckCircle2 size={16} className="mt-0.5 shrink-0" /> Graph API Explorer ile token ve ID degerlerini al.</li>
                                <li className="flex items-start gap-2"><CheckCircle2 size={16} className="mt-0.5 shrink-0" /> .env dosyasina degerleri yapistir.</li>
                            </ul>
                        </div>

                        {/* Links */}
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                            <a href="https://developers.facebook.com/apps/" target="_blank" rel="noreferrer" className="rounded-xl border border-gray-200 dark:border-white/10 p-3 bg-gray-50 dark:bg-dark-900 hover:bg-gray-100 dark:hover:bg-dark-700 transition">
                                <p className="font-semibold text-gray-900 dark:text-white inline-flex items-center gap-2"><ExternalLink size={14} /> Meta Developers</p>
                                <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">App / Use Case / Explorer</p>
                            </a>
                            <a href="https://business.facebook.com/settings/" target="_blank" rel="noreferrer" className="rounded-xl border border-gray-200 dark:border-white/10 p-3 bg-gray-50 dark:bg-dark-900 hover:bg-gray-100 dark:hover:bg-dark-700 transition">
                                <p className="font-semibold text-gray-900 dark:text-white inline-flex items-center gap-2"><Globe size={14} /> Business Settings</p>
                                <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">Page / IG / App baglantilari</p>
                            </a>
                        </div>

                        {/* Graph Config Inputs */}
                        <div className="rounded-2xl border border-gray-200 dark:border-white/10 bg-gray-50 dark:bg-dark-900 p-4 space-y-3">
                            <p className="font-semibold text-gray-900 dark:text-white">Graph alanlarini UI'dan kaydet</p>
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                                <input className="w-full bg-white dark:bg-dark-800 border border-gray-300 dark:border-white/10 rounded-xl p-3 text-sm text-gray-900 dark:text-white" placeholder="FB_APP_ID" value={graphConfig.fb_app_id} onChange={(e) => setGraphConfig(prev => ({ ...prev, fb_app_id: e.target.value }))} />
                                <input className="w-full bg-white dark:bg-dark-800 border border-gray-300 dark:border-white/10 rounded-xl p-3 text-sm text-gray-900 dark:text-white" placeholder="FB_APP_SECRET" value={graphConfig.fb_app_secret} onChange={(e) => setGraphConfig(prev => ({ ...prev, fb_app_secret: e.target.value }))} />
                                <input className="w-full bg-white dark:bg-dark-800 border border-gray-300 dark:border-white/10 rounded-xl p-3 text-sm text-gray-900 dark:text-white" placeholder="FB_PAGE_ID" value={graphConfig.fb_page_id} onChange={(e) => setGraphConfig(prev => ({ ...prev, fb_page_id: e.target.value }))} />
                                <input className="w-full bg-white dark:bg-dark-800 border border-gray-300 dark:border-white/10 rounded-xl p-3 text-sm text-gray-900 dark:text-white" placeholder="IG_USER_ID" value={graphConfig.ig_user_id} onChange={(e) => setGraphConfig(prev => ({ ...prev, ig_user_id: e.target.value }))} />
                            </div>
                            <input className="w-full bg-white dark:bg-dark-800 border border-gray-300 dark:border-white/10 rounded-xl p-3 text-sm text-gray-900 dark:text-white" placeholder="FB_ACCESS_TOKEN" value={graphConfig.fb_access_token} onChange={(e) => setGraphConfig(prev => ({ ...prev, fb_access_token: e.target.value }))} />
                            <input className="w-full bg-white dark:bg-dark-800 border border-gray-300 dark:border-white/10 rounded-xl p-3 text-sm text-gray-900 dark:text-white" placeholder="PUBLIC_BASE_URL (https://....trycloudflare.com)" value={graphConfig.public_base_url} onChange={(e) => setGraphConfig(prev => ({ ...prev, public_base_url: e.target.value }))} />
                            <div className="flex gap-2">
                                <button onClick={saveGraphConfig} className="px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-semibold text-sm">UI'dan .env Kaydet</button>
                                <button
                                    onClick={async () => {
                                        await refreshGraphStatus();
                                        await refreshGraphTokenStatus();
                                        await refreshImgBBConfig();
                                    }}
                                    className="px-4 py-2 rounded-lg border border-gray-300 dark:border-white/20 text-gray-700 dark:text-gray-200 text-sm"
                                >
                                    Durumu Yenile
                                </button>
                            </div>
                        </div>

                        {/* ImgBB Fallback */}
                        <div className="rounded-2xl border border-emerald-200 dark:border-emerald-500/30 bg-emerald-50 dark:bg-emerald-500/10 p-4 space-y-3">
                            <div className="flex items-center justify-between gap-3">
                                <div>
                                    <p className="font-semibold text-emerald-700 dark:text-emerald-300">ImgBB Fallback (Cloudflare yedegi)</p>
                                    <p className="text-xs text-emerald-900/80 dark:text-emerald-100/90 mt-1">Tunnel linki fail olursa gorsel gecici olarak ImgBB'ye yuklenir.</p>
                                </div>
                                <span className={`text-xs font-bold px-2 py-1 rounded-md ${imgbbConfigured ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/20 dark:text-emerald-300' : 'bg-amber-100 text-amber-700 dark:bg-amber-500/20 dark:text-amber-300'}`}>
                                    {imgbbConfigured ? 'Hazir' : 'Eksik'}
                                </span>
                            </div>
                            <input
                                type="password"
                                className="w-full bg-white dark:bg-dark-800 border border-emerald-300/60 dark:border-emerald-400/30 rounded-xl p-3 text-sm text-gray-900 dark:text-white"
                                placeholder="IMGBB_API_KEY"
                                value={imgbbApiKey}
                                onChange={(e) => setImgbbApiKey(e.target.value)}
                            />
                            <div className="flex gap-2">
                                <button onClick={saveImgBBConfig} className="px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white font-semibold text-sm">ImgBB anahtarini .env kaydet</button>
                                <button onClick={refreshImgBBConfig} className="px-4 py-2 rounded-lg border border-emerald-300/70 dark:border-emerald-400/30 text-emerald-700 dark:text-emerald-300 text-sm">Yenile</button>
                            </div>
                        </div>

                        {/* .env Template */}
                        <div className="rounded-2xl border border-gray-200 dark:border-white/10 bg-gray-50 dark:bg-dark-900 p-4">
                            <div className="flex items-center justify-between gap-3 mb-3">
                                <p className="font-semibold text-gray-900 dark:text-white inline-flex items-center gap-2"><Link2 size={16} /> .env sablonu</p>
                                <button
                                    onClick={copyGraphEnvTemplate}
                                    className="px-3 py-1.5 rounded-lg text-xs font-semibold border border-gray-300 dark:border-white/20 hover:bg-gray-200 dark:hover:bg-dark-700 transition inline-flex items-center gap-1 text-gray-700 dark:text-gray-200"
                                >
                                    <Copy size={13} /> {envCopied ? 'Kopyalandi' : 'Kopyala'}
                                </button>
                            </div>
                            <pre className="text-xs leading-5 text-gray-700 dark:text-gray-300 bg-white dark:bg-black/30 border border-gray-200 dark:border-white/10 rounded-xl p-3 overflow-x-auto">{graphEnvTemplate}</pre>
                        </div>
                    </div>
                )}

                {/* Legacy Tab */}
                {instaAuthTab === 'legacy' && (
                    <div className="space-y-3 text-left">
                        <p className="text-sm dark:text-gray-400 text-gray-500">
                            Sifre projeye yazilmaz. Windows Credential Manager'a kaydedilir.
                        </p>
                        <input
                            className="w-full bg-gray-50 dark:bg-dark-900/50 border border-gray-300 dark:border-white/10 rounded-xl p-3 text-gray-900 dark:text-white focus:border-emerald-500 focus:outline-none"
                            placeholder="Kullanici adi"
                            value={instaUser}
                            onChange={(e) => setInstaUser(e.target.value)}
                        />
                        <input
                            type="password"
                            className="w-full bg-gray-50 dark:bg-dark-900/50 border border-gray-300 dark:border-white/10 rounded-xl p-3 text-gray-900 dark:text-white focus:border-emerald-500 focus:outline-none"
                            placeholder="Sifre"
                            value={instaPass}
                            onChange={(e) => setInstaPass(e.target.value)}
                        />
                        <div className="flex gap-3 pt-2">
                            <button
                                onClick={async () => {
                                    if (!instaUser.trim() || !instaPass) return;
                                    const res = await api.saveInstagramCredentials(instaUser.trim(), instaPass);
                                    if (res?.success) {
                                        await api.resetInstagramSession();
                                        closeInstaModal();
                                        alert('Kaydedildi. Oturum sifirlandi. Bir sonraki upload taze login ile yapilacak.');
                                    } else {
                                        alert('Hata: ' + (res?.error || 'Kaydedilemedi'));
                                    }
                                }}
                                className="flex-1 py-3 rounded-xl font-bold bg-emerald-600 hover:bg-emerald-700 text-white transition-colors"
                            >
                                Kaydet
                            </button>
                            <button
                                onClick={async () => {
                                    const ok = window.confirm("Instagram oturum dosyasi (insta_session.json) sifirlansin mi?");
                                    if (!ok) return;
                                    const res = await api.resetInstagramSession();
                                    alert(res?.success ? 'Oturum sifirlandi.' : 'Sifirlanamadi.');
                                }}
                                className="px-4 py-3 rounded-xl border border-gray-300 dark:border-white/10 bg-gray-100 dark:bg-dark-900 hover:bg-gray-200 dark:hover:bg-dark-800 transition-colors text-gray-800 dark:text-white"
                            >
                                Oturumu Sifirla
                            </button>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}
