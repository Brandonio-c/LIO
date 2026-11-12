// lio_ocr: read the text in an image with Apple Vision (on-device; nothing leaves the Mac).
// Usage: lio_ocr <image>. Prints a JSON array of lines: {text, conf, x, y, w, h}
// (box in normalised image coordinates, origin bottom-left). Built on first use by
// lio.foods.ocr with `xcrun swiftc -O lio_ocr.swift -o <cache>/lio_ocr`.
import Foundation
import ImageIO
import Vision

func fail(_ msg: String, _ code: Int32) -> Never {
    FileHandle.standardError.write((msg + "\n").data(using: .utf8)!)
    exit(code)
}

let args = CommandLine.arguments
guard args.count > 1,
      let src = CGImageSourceCreateWithURL(URL(fileURLWithPath: args[1]) as CFURL, nil),
      let img = CGImageSourceCreateImageAtIndex(src, 0, nil)
else { fail("usage: lio_ocr <image>", 2) }

func recognise(cpuOnly: Bool) throws -> [VNRecognizedTextObservation] {
    let req = VNRecognizeTextRequest()
    req.recognitionLevel = .accurate
    req.usesLanguageCorrection = true
    if cpuOnly { req.usesCPUOnly = true }  // fallback when the neural engine is unavailable
    try VNImageRequestHandler(cgImage: img, options: [:]).perform([req])
    return req.results ?? []
}

var results: [VNRecognizedTextObservation]
do { results = try recognise(cpuOnly: false) } catch {
    do { results = try recognise(cpuOnly: true) } catch { fail("vision: \(error)", 1) }
}
var out: [[String: Any]] = []
for obs in results {
    guard let c = obs.topCandidates(1).first else { continue }
    let b = obs.boundingBox
    out.append(["text": c.string, "conf": c.confidence,
                "x": b.origin.x, "y": b.origin.y, "w": b.size.width, "h": b.size.height])
}
FileHandle.standardOutput.write(try! JSONSerialization.data(withJSONObject: out))
