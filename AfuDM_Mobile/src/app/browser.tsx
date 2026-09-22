import React, { useRef, useState } from 'react';
import { View, StyleSheet, TouchableOpacity, Text, SafeAreaView, TextInput, ActivityIndicator } from 'react-native';
import { WebView } from 'react-native-webview';
import { downloadManager } from '../services/DownloadService';

export default function BrowserScreen() {
  const webviewRef = useRef<WebView>(null);
  const [url, setUrl] = useState('https://google.com');
  const [inputUrl, setInputUrl] = useState('https://google.com');
  const [videoFound, setVideoFound] = useState(false);
  const [foundVideoUrl, setFoundVideoUrl] = useState('');
  const [isCobaltLoading, setIsCobaltLoading] = useState(false);

  // JavaScript to inject into every page to find <video> tags
  const injectedJavaScript = `
    (function() {
      setInterval(() => {
        const videos = document.getElementsByTagName('video');
        if (videos.length > 0) {
          const src = videos[0].src || videos[0].currentSrc;
          if (src && !src.startsWith('blob:')) {
            window.ReactNativeWebView.postMessage(JSON.stringify({ type: 'VIDEO_FOUND', url: src }));
          }
        }
      }, 1000);
    })();
    true;
  `;

  const onMessage = (event: any) => {
    try {
      const data = JSON.parse(event.nativeEvent.data);
      if (data.type === 'VIDEO_FOUND' && data.url) {
        setVideoFound(true);
        setFoundVideoUrl(data.url);
      }
    } catch (e) {}
  };

  const handleSnifferDownload = () => {
    alert('İndirme kuyruğuna eklendi: ' + foundVideoUrl);
    downloadManager.startDownload(foundVideoUrl, 'SnifferVideo_' + Date.now() + '.mp4');
    setVideoFound(false);
  };

  const handleCobaltDownload = async () => {
    setIsCobaltLoading(true);
    try {
      const response = await fetch('https://api.cobalt.tools/api/json', {
        method: 'POST',
        headers: {
          'Accept': 'application/json',
          'Content-Type': 'application/json',
          'Origin': 'https://cobalt.tools',
          'Referer': 'https://cobalt.tools/',
          'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        },
        body: JSON.stringify({
          url: url,
          vQuality: '1080',
          vCodec: 'h264',
          filenamePattern: 'classic'
        })
      });
      const data = await response.json();
      
      if (data.status === 'error') {
        alert('Hata: ' + data.text);
      } else if (data.url) {
        alert('Cobalt: Link bulundu, indiriliyor!');
        downloadManager.startDownload(data.url, 'CobaltVideo_' + Date.now() + '.mp4');
      }
    } catch (error) {
      alert('Cobalt API bağlantı hatası');
    }
    setIsCobaltLoading(false);
  };

  const isSocialMedia = url.includes('youtube.com') || url.includes('youtu.be') || url.includes('instagram.com') || url.includes('tiktok.com');

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.addressBar}>
        <TextInput 
          style={styles.input} 
          value={inputUrl} 
          onChangeText={setInputUrl}
          onSubmitEditing={() => setUrl(inputUrl.startsWith('http') ? inputUrl : 'https://' + inputUrl)}
          autoCapitalize="none"
          keyboardType="url"
        />
        <TouchableOpacity style={styles.goBtn} onPress={() => setUrl(inputUrl.startsWith('http') ? inputUrl : 'https://' + inputUrl)}>
          <Text style={{color: '#fff'}}>Git</Text>
        </TouchableOpacity>
      </View>
      <WebView 
        ref={webviewRef}
        source={{ uri: url }} 
        style={styles.webview}
        injectedJavaScript={injectedJavaScript}
        onMessage={onMessage}
        allowsInlineMediaPlayback={true}
        mediaPlaybackRequiresUserAction={false}
        onNavigationStateChange={(navState) => {
          setUrl(navState.url);
          setInputUrl(navState.url);
        }}
      />
      
      {isSocialMedia && (
        <TouchableOpacity style={styles.cobaltBtn} onPress={handleCobaltDownload}>
          {isCobaltLoading ? <ActivityIndicator color="#fff" /> : <Text style={styles.btnText}>⚡ Cobalt İle İndir</Text>}
        </TouchableOpacity>
      )}

      {videoFound && !isSocialMedia && (
        <TouchableOpacity style={styles.downloadBtn} onPress={handleSnifferDownload}>
          <Text style={styles.btnText}>⬇ İndir (Sniffer)</Text>
        </TouchableOpacity>
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0f131a' },
  addressBar: { flexDirection: 'row', padding: 10, backgroundColor: '#14181f', alignItems: 'center', borderBottomWidth: 1, borderBottomColor: '#2a3340' },
  input: { flex: 1, backgroundColor: '#1c222c', color: '#e6eaf0', padding: 8, borderRadius: 2, marginRight: 8, borderWidth: 1, borderColor: '#2a3340' },
  goBtn: { backgroundColor: '#5b9dff', padding: 10, borderRadius: 2 },
  webview: { flex: 1, backgroundColor: '#0f131a' },
  cobaltBtn: {
    position: 'absolute',
    bottom: 20,
    left: 20,
    backgroundColor: '#8a2be2',
    paddingVertical: 12,
    paddingHorizontal: 20,
    borderRadius: 30,
    elevation: 5,
  },
  downloadBtn: {
    position: 'absolute',
    bottom: 20,
    right: 20,
    backgroundColor: '#ff3b30',
    paddingVertical: 12,
    paddingHorizontal: 20,
    borderRadius: 30,
    elevation: 5,
  },
  btnText: { color: '#fff', fontWeight: 'bold', fontSize: 16 }
});
