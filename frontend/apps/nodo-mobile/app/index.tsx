import { SafeAreaView, StyleSheet, Text, View } from "react-native";

export default function TodayScreen() {
  return (
    <SafeAreaView style={styles.screen}>
      <View style={styles.content}>
        <Text style={styles.brand}>NODO</Text>
        <Text style={styles.title}>Tu entrenamiento de hoy</Text>
        <Text style={styles.copy}>La primera pantalla del atleta mostrará su sesión, recuperación y check-in antes de entrenar.</Text>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: "#10231b" },
  content: { flex: 1, justifyContent: "center", padding: 28 },
  brand: { color: "#8ee0ad", fontSize: 14, fontWeight: "700", letterSpacing: 2 },
  title: { color: "#eaf1ec", fontSize: 38, fontWeight: "700", marginTop: 12 },
  copy: { color: "#bfd1c4", fontSize: 18, lineHeight: 28, marginTop: 18 },
});
