import * as FileSystem from 'expo-file-system';

export interface DownloadItem {
  id: string;
  url: string;
  title: string;
  progress: number;
  status: 'Downloading' | 'Finished' | 'Error';
  fileUri?: string;
}

class DownloadManager {
  downloads: DownloadItem[] = [];
  listeners: (() => void)[] = [];

  subscribe(listener: () => void) {
    this.listeners.push(listener);
    return () => {
      this.listeners = this.listeners.filter(l => l !== listener);
    };
  }

  notify() {
    for (let listener of this.listeners) {
      listener();
    }
  }

  async startDownload(url: string, filename: string) {
    const id = Date.now().toString();
    const fileUri = FileSystem.documentDirectory + filename;
    
    const newDownload: DownloadItem = {
      id, url, title: filename, progress: 0, status: 'Downloading', fileUri
    };
    
    this.downloads = [newDownload, ...this.downloads];
    this.notify();

    const downloadResumable = FileSystem.createDownloadResumable(
      url,
      fileUri,
      {},
      (downloadProgress) => {
        const progress = (downloadProgress.totalBytesWritten / downloadProgress.totalBytesExpectedToWrite) * 100;
        const index = this.downloads.findIndex(d => d.id === id);
        if (index > -1) {
          this.downloads[index].progress = progress;
          this.notify();
        }
      }
    );

    try {
      const result = await downloadResumable.downloadAsync();
      if (result) {
        const index = this.downloads.findIndex(d => d.id === id);
        if (index > -1) {
          this.downloads[index].status = 'Finished';
          this.notify();
        }
        // Try to save to gallery if it's media (Temporarily disabled due to Expo Go native module limitations)
        // const { status } = await MediaLibrary.requestPermissionsAsync();
        // if (status === 'granted') {
        //   await MediaLibrary.createAssetAsync(result.uri);
        // }
      }
    } catch (e) {
      const index = this.downloads.findIndex(d => d.id === id);
      if (index > -1) {
        this.downloads[index].status = 'Error';
        this.notify();
      }
    }
  }
}

export const downloadManager = new DownloadManager();
