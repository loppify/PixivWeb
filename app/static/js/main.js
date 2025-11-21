import PhotoSwipeLightbox from 'https://unpkg.com/photoswipe@latest/dist/photoswipe-lightbox.esm.js';
import PhotoSwipe from 'https://unpkg.com/photoswipe@latest/dist/photoswipe.esm.js';

document.addEventListener('DOMContentLoaded', () => {
    const downloadForm = document.getElementById('download-form');
    const startButton = document.getElementById('start-button');
    const statusMessage = document.getElementById('status-message');
    const galleryGrid = document.getElementById('gallery-grid');
    const loadingMessage = document.getElementById('loading-message');
    const refreshButton = document.getElementById('refresh-button');
    const galleryFooter = document.getElementById('gallery-footer');
    const favFilter = document.getElementById('fav-filter');
    const deleteBtn = document.getElementById('delete-viewed-btn');

    let files = [];
    let page = 1;
    let isLoading = false;
    let hasMore = true;
    let lightbox = null;
    let autoSyncInterval = null;

    function setStatus(text, kind) {
        statusMessage.textContent = text;
        statusMessage.className = '';
        statusMessage.classList.add(kind === 'success' ? 'text-green-400' : kind === 'error' ? 'text-red-400' : 'text-sky-400');
    }

    async function syncLibrary() {
        setStatus('Syncing library...', 'loading');
        try {
            const res = await fetch('/api/sync', { method: 'POST' });
            const data = await res.json();
            if (data.added > 0 || data.removed > 0) {
                setStatus(`Synced: +${data.added} / -${data.removed}`, 'success');
                return true;
            } else {
                setStatus('Library up to date', 'success');
                return false;
            }
        } catch (e) {
            console.error(e);
            return false;
        }
    }

    async function toggleFavorite(filename) {
        try {
            const res = await fetch('/api/toggle-favorite', {
                method: 'POST', headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({filename})
            });
            const data = await res.json();
            if (data.status === 'success') return data.favorite;
        } catch (e) {
            console.error(e);
        }
        return false;
    }

    async function markAsViewed(filename, el) {
        try {
            await fetch('/api/mark-viewed', {
                method: 'POST', headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({filename})
            });
            if (el) el.classList.add('viewed-item');
            const fileObj = files.find(f => f.name === filename);
            if (fileObj) fileObj.viewed = true;
        } catch (e) {
            console.error(e);
        }
    }

    async function fetchImages(reset = false, runSync = false) {
        if (isLoading) return;

        if (runSync) {
            await syncLibrary();
        }

        if (reset) {
            galleryGrid.innerHTML = '';
            files = [];
            page = 1;
            hasMore = true;
        }

        if (!hasMore && !reset) return;

        isLoading = true;
        loadingMessage.style.display = 'block';
        const showFavs = favFilter.checked;

        try {
            const res = await fetch(`/api/images?page=${page}&limit=30&favorites=${showFavs}&_t=${Date.now()}`);
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data = await res.json();

            const loadPromises = [];

            for (const fileObj of data.files) {
                files.push(fileObj);
                const filename = fileObj.name;
                const src = `/downloads/${filename}`;
                const ext = filename.split('.').pop().toLowerCase();

                const container = document.createElement('div');
                container.className = `gallery-item-container ${fileObj.favorite ? 'is-favorite' : ''}`;
                container.dataset.filename = filename;

                const heart = document.createElement('div');
                heart.className = 'grid-heart';
                heart.innerHTML = '❤';
                container.appendChild(heart);

                let el;
                if (!['mp4', 'webm'].includes(ext)) {
                    el = document.createElement('img');
                    el.src = src;
                    el.loading = 'lazy';
                    el.className = `gallery-item ${fileObj.viewed ? 'viewed-item' : ''}`;
                    const p = Promise.race([
                        el.decode().catch(() => {}),
                        new Promise(r => setTimeout(r, 3000))
                    ]);
                    loadPromises.push(p);
                } else {
                    el = document.createElement('video');
                    el.src = src;
                    el.loop = true;
                    el.muted = true;
                    el.preload = 'metadata';
                    el.className = `gallery-item ${fileObj.viewed ? 'viewed-item' : ''}`;

                    const p = new Promise(resolve => {
                        const finish = () => resolve();
                        el.onloadedmetadata = finish;
                        el.onerror = finish;
                        setTimeout(finish, 3000);
                    });
                    el.onmouseenter = () => el.play();
                    el.onmouseleave = () => el.pause();
                    loadPromises.push(p);
                }

                el.addEventListener('click', (e) => {
                    const allContainers = [...galleryGrid.querySelectorAll('.gallery-item-container')];
                    const realIndex = allContainers.indexOf(e.target.parentElement);
                    if (realIndex >= 0) openLightbox(realIndex);
                });

                container.appendChild(el);
                galleryGrid.appendChild(container);
                viewObserver.observe(el);
            }

            await Promise.all(loadPromises);

            if (data.has_more) {
                page++;
                hasMore = true;
            } else {
                hasMore = false;
                loadingMessage.style.display = 'none';
            }

        } catch (err) {
            loadingMessage.textContent = 'Error loading images';
        } finally {
            isLoading = false;
        }
    }

    function buildDataSource() {
        return files.map(fileObj => {
            const src = `/downloads/${fileObj.name}`;
            const ext = fileObj.name.split('.').pop().toLowerCase();
            const match = fileObj.name.match(/_\[(\d+)_/) || fileObj.name.match(/(\d+)_p/);
            const id = match ? match[1] : null;
            const isVideo = ['mp4', 'webm'].includes(ext);
            const safeWidth = fileObj.width > 0 ? fileObj.width : 800;
            const safeHeight = fileObj.height > 0 ? fileObj.height : 800;

            if (isVideo) {
                return {
                    type: 'html',
                    html: `<div class="pswp-video-container"><video src="${src}" controls autoplay loop muted playsinline></video></div>`,
                    width: 1920,
                    height: 1080,
                    data: { illustId: id, filename: fileObj.name, favorite: fileObj.favorite, isVideo: true }
                };
            } else {
                return {
                    src: src,
                    msrc: src,
                    width: safeWidth,
                    height: safeHeight,
                    data: {
                        src: src,
                        illustId: id,
                        filename: fileObj.name,
                        favorite: fileObj.favorite,
                        isVideo: false
                    }
                };
            }
        });
    }

    function openLightbox(index) {
        if (lightbox) lightbox.destroy();

        lightbox = new PhotoSwipeLightbox({
            pswpModule: PhotoSwipe,
            dataSource: buildDataSource(),
            paddingFn: () => 20,
            wheelToZoom: true,
            allowPanToNext: false,
            thumbEl: (itemData, index) => {
                const currentFile = files[index];
                if(!currentFile) return null;
                const container = document.querySelector(`div[data-filename="${currentFile.name}"]`);
                if(container) {
                    return container.querySelector('img') || container.querySelector('video');
                }
                return null;
            }
        });

        lightbox.on('uiRegister', () => {
            lightbox.pswp.ui.registerElement({
                name: 'copyButton', order: 8, isButton: true,
                title: 'Copy Pixiv Link', html: 'Copy Link',
                onClick: (e, el, pswp) => {

                    const id = pswp.currSlide?.data?.data?.illustId;
                    try {
                        const url = `https://www.pixiv.net/en/artworks/${id}`;
                        navigator.clipboard.writeText(url).then(() => {
                            el.innerHTML = 'Copied!';
                            setTimeout(() => el.innerHTML = 'Copy Link', 1200);
                        });
                    } catch (err) {
                        el.innerHTML = 'Pasted to field';
                        document.getElementById('url-input').value = `https://www.pixiv.net/en/artworks/${id}`
                        setTimeout(() => el.innerHTML = 'Copy Link', 1200);
                    }
                }
            });

            lightbox.pswp.ui.registerElement({
                name: 'favButton', order: 9, isButton: true,
                title: 'Favorite', html: 'Fav',
                onInit: (el, pswp) => {
                    const isFav = pswp.currSlide?.data?.data?.favorite;
                    if (isFav) {
                        el.innerHTML = 'Liked';
                        el.classList.add('active');
                    }
                },
                onClick: async (e, el, pswp) => {
                    const filename = pswp.currSlide?.data?.data?.filename;
                    const newStatus = await toggleFavorite(filename);

                    el.innerHTML = newStatus ? 'Liked' : 'Fav';
                    el.classList.toggle('active', newStatus);

                    const fileObj = files.find(f => f.name === filename);
                    if (fileObj) fileObj.favorite = newStatus;

                    const gridContainer = document.querySelector(`div[data-filename="${filename}"]`);
                    if (gridContainer) {
                        if (newStatus) gridContainer.classList.add('is-favorite');
                        else gridContainer.classList.remove('is-favorite');
                    }
                }
            });
        });

        lightbox.on('change', () => {
            const pswp = lightbox.pswp;
            const favBtn = document.querySelector('.pswp__button--favButton');
            const isFav = pswp.currSlide?.data?.data?.favorite;

            if (favBtn) {
                favBtn.innerHTML = isFav ? 'Liked' : 'Fav';
                favBtn.classList.toggle('active', isFav);
            }

            const filename = pswp.currSlide?.data?.data?.filename;
            if (filename) {
                const gridImg = document.querySelector(`div[data-filename="${filename}"] .gallery-item`);
                markAsViewed(filename, gridImg);
            }
        });

        lightbox.init();
        lightbox.loadAndOpen(index);
    }

    const viewObserver = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const container = entry.target.parentElement;
                const filename = container.dataset.filename;
                markAsViewed(filename, entry.target);
                viewObserver.unobserve(entry.target);
            }
        });
    }, {threshold: 0.6});

    const scrollObserver = new IntersectionObserver(entries => {
        if (entries[0].isIntersecting && !isLoading && hasMore) fetchImages(false, false);
    });
    scrollObserver.observe(galleryFooter);

    downloadForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const url = document.getElementById('url-input').value.trim();
        const depth = parseInt(document.getElementById('depth-input').value, 10);
        if (!url) return;

        startButton.disabled = true;
        setStatus('Starting download...', 'loading');

        try {
            const res = await fetch('/api/start-download', {
                method: 'POST', headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({url, depth})
            });
            const data = await res.json();
            setStatus(data.message, 'success');
            document.getElementById('url-input').value = '';

            let checks = 0;
            if (autoSyncInterval) clearInterval(autoSyncInterval);

            autoSyncInterval = setInterval(async () => {
                checks++;
                const changed = await syncLibrary();
                if (changed) {
                    setStatus('New files detected!', 'success');
                }
                if (checks > 60) clearInterval(autoSyncInterval);
            }, 4000);

        } catch (err) {
            setStatus('Error starting download', 'error');
        } finally {
            startButton.disabled = false;
        }
    });

    deleteBtn.addEventListener('click', async () => {
        if (!confirm("Delete all VIEWED images that are NOT favorites?")) return;
        try {
            const res = await fetch('/api/delete-viewed', {method: 'POST'});
            const d = await res.json();
            alert(`Deleted ${d.deleted} images.`);
            fetchImages(true, true);
        } catch (e) {
            alert("Error deleting.");
        }
    });

    refreshButton.addEventListener('click', () => {
        fetchImages(true, true);
    });

    favFilter.addEventListener('change', () => fetchImages(true, false));

    (async () => {
        await syncLibrary();
        fetchImages(true, false);
    })();
});