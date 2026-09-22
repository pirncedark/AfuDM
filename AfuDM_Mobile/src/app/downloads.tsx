import React, { useState, useEffect } from 'react';
import { View, StyleSheet, Text, SafeAreaView, FlatList, TouchableOpacity } from 'react-native';
import { downloadManager, DownloadItem } from '../services/DownloadService';

export default function DownloadsScreen() {
  const [downloads, setDownloads] = useState<DownloadItem[]>([]);

  useEffect(() => {
    // Initial load
    setDownloads([...downloadManager.downloads]);
    
    // Subscribe to changes
    const unsubscribe = downloadManager.subscribe(() => {
      setDownloads([...downloadManager.downloads]);
    });

    return () => unsubscribe();
  }, []);

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.headerText}>İndirmeler (ADM Engine)</Text>
      </View>
      <FlatList
        data={downloads}
        keyExtractor={item => item.id}
        renderItem={({ item }) => (
          <View style={styles.row}>
            <Text style={styles.title}>{item.title}</Text>
            
            {item.status === 'Downloading' ? (
              <View style={styles.progressContainer}>
                <View style={[styles.progressBar, { width: `${item.progress}%` }]} />
              </View>
            ) : (
              <Text style={styles.statusText}>
                {item.status === 'Finished' ? '✅ İndirme Tamamlandı' : '❌ Hata Oluştu'}
              </Text>
            )}

            {item.status === 'Downloading' && (
              <View style={styles.details}>
                <Text style={styles.detailText}>{item.progress.toFixed(1)}%</Text>
                <Text style={styles.detailText}>İndiriliyor...</Text>
              </View>
            )}
          </View>
        )}
        ListEmptyComponent={
          <View style={{padding: 20, alignItems: 'center'}}>
            <Text style={{color: '#888'}}>Henüz indirme yok.</Text>
          </View>
        }
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#14181f' },
  header: { padding: 16, backgroundColor: '#0f131a', borderBottomWidth: 1, borderBottomColor: '#2a3340' },
  headerText: { color: '#e6eaf0', fontSize: 18, fontWeight: 'bold' },
  row: { padding: 12, borderBottomWidth: 1, borderBottomColor: '#222a35', backgroundColor: '#1c222c', marginBottom: 2 },
  title: { color: '#e6eaf0', fontSize: 14, marginBottom: 8 },
  progressContainer: { height: 6, backgroundColor: '#ffffff0a', borderRadius: 2, overflow: 'hidden', marginBottom: 8 },
  progressBar: { height: '100%', backgroundColor: '#5b9dff' },
  details: { flexDirection: 'row', justifyContent: 'space-between' },
  detailText: { color: '#8a97a8', fontSize: 12, fontFamily: 'monospace' },
  statusText: { color: '#8a97a8', fontSize: 12, fontStyle: 'italic', fontFamily: 'monospace' }
});
