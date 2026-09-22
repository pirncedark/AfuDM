import { Tabs } from 'expo-router';
import { useColorScheme } from 'react-native';
import { Colors } from '@/constants/theme';

// SplashScreen removed for direct loading

export default function TabLayout() {
  const scheme = useColorScheme();
  const colors = Colors[scheme === 'unspecified' ? 'light' : scheme];

  return (
    <Tabs screenOptions={{
      headerShown: false,
      tabBarStyle: { backgroundColor: colors.background, borderTopColor: '#1b1d22' },
      tabBarActiveTintColor: colors.text,
      tabBarInactiveTintColor: '#888',
      tabBarLabelStyle: { fontSize: 12, fontWeight: 'bold' }
    }}>
      <Tabs.Screen
        name="browser"
        options={{
          title: 'Tarayıcı',
          tabBarIcon: () => null,
        }}
      />
      <Tabs.Screen
        name="downloads"
        options={{
          title: 'İndirmeler',
          tabBarIcon: () => null,
        }}
      />
      <Tabs.Screen
        name="index"
        options={{
          href: null,
        }}
      />
    </Tabs>
  );
}
