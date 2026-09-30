import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';
import 'models.dart';

/// Backend-ийн хаяг. Android emulator дээр компьютерийн localhost = 10.0.2.2
const String kApiBase = String.fromEnvironment('API_BASE', defaultValue: 'http://10.0.2.2:8000');

class Api {
  String? _token;

  Future<String> _getToken() async {
    if (_token != null) return _token!;
    final prefs = await SharedPreferences.getInstance();
    _token = prefs.getString('token');
    if (_token != null) return _token!;
    final r = await http.post(Uri.parse('$kApiBase/api/v1/auth/anonymous')).timeout(const Duration(seconds: 5));
    _token = (jsonDecode(r.body) as Map<String, dynamic>)['token'] as String;
    await prefs.setString('token', _token!);
    return _token!;
  }

  Future<Assessment> assess({
    required int gaWeek,
    required List<Contraction> contractions,
    required Set<String> symptoms,
    String? freeText,
  }) async {
    final sw = Stopwatch()..start();
    final body = jsonEncode({
      'ga_week': gaWeek,
      'contractions': contractions.map((c) => c.toJson()).toList(),
      'checkbox_symptoms': symptoms.toList(),
      'free_text': (freeText == null || freeText.trim().isEmpty) ? null : freeText.trim(),
      'now': DateTime.now().millisecondsSinceEpoch / 1000.0,
    });
    final r = await http
        .post(Uri.parse('$kApiBase/api/v1/assess'),
            headers: {'Content-Type': 'application/json', 'Authorization': 'Bearer ${await _getToken()}'},
            body: body)
        .timeout(const Duration(seconds: 5));
    if (r.statusCode == 401) {
      _token = null;
      (await SharedPreferences.getInstance()).remove('token');
    }
    if (r.statusCode != 200) throw Exception('API ${r.statusCode}');
    return Assessment.fromJson(jsonDecode(utf8.decode(r.bodyBytes)) as Map<String, dynamic>, sw.elapsedMilliseconds);
  }
}
