import 'dart:convert';

/// Нэг агшилтын бичлэг (Unix секундээр).
class Contraction {
  final double start;
  final double end;
  final int? pain;
  const Contraction({required this.start, required this.end, this.pain});

  double get duration => end - start;

  Map<String, dynamic> toJson() => {'start': start, 'end': end, 'pain': pain};
  factory Contraction.fromJson(Map<String, dynamic> j) => Contraction(
      start: (j['start'] as num).toDouble(),
      end: (j['end'] as num).toDouble(),
      pain: j['pain'] == null ? null : (j['pain'] as num).toInt());

  static String encodeList(List<Contraction> xs) => jsonEncode(xs.map((c) => c.toJson()).toList());
  static List<Contraction> decodeList(String s) =>
      (jsonDecode(s) as List).map((e) => Contraction.fromJson(e as Map<String, dynamic>)).toList();
}

const Map<String, String> kSymptoms = {
  'bleeding': 'Цус гарах',
  'fluid_leak': 'Ус/шингэн гоожих',
  'reduced_movement': 'Хүүхэд хөдлөхгүй',
  'severe_pain': 'Тасралтгүй хүчтэй өвдөлт',
  'fever': 'Халуурах',
  'headache_vision': 'Толгой өвдөх/хараа бүрэлзэх',
  'back_pain': 'Нуруу өвдөх',
  'pelvic_pressure': 'Аарцаг дарагдах',
  'pain_increasing': 'Өвдөлт нэмэгдэх',
};
const List<String> kRedFlags = [
  'bleeding', 'fluid_leak', 'reduced_movement', 'severe_pain', 'fever', 'headache_vision'
];

class Assessment {
  final String level; // LOW | MEDIUM | HIGH
  final String advice;
  final List<String> explanations;
  final List<String> nlpSymptoms;
  final String disclaimer;
  final bool offline;
  final int? rttMs;
  Assessment({
    required this.level,
    required this.advice,
    this.explanations = const [],
    this.nlpSymptoms = const [],
    this.disclaimer = 'Энэ нь эмнэлгийн онош биш.',
    this.offline = false,
    this.rttMs,
  });

  factory Assessment.fromJson(Map<String, dynamic> j, int rtt) => Assessment(
        level: j['risk_level'] as String,
        advice: j['advice'] as String,
        explanations: List<String>.from(j['explanations'] as List),
        nlpSymptoms: List<String>.from(j['nlp_symptoms'] as List),
        disclaimer: j['disclaimer'] as String,
        rttMs: rtt,
      );
}
