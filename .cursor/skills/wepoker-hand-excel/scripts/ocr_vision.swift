import Foundation
import Vision
import AppKit

// Usage: swift ocr_vision.swift <image...>
// or:    swift ocr_vision.swift list.txt
// Prints JSON array of {path, text, x, y, w, h, conf}

struct Box: Encodable {
    let path: String
    let text: String
    let x: Double
    let y: Double
    let w: Double
    let h: Double
    let conf: Double
}

func ocr(_ path: String) -> [Box] {
    let url = URL(fileURLWithPath: path)
    guard let ns = NSImage(contentsOf: url),
          let tiff = ns.tiffRepresentation,
          let rep = NSBitmapImageRep(data: tiff),
          let cg = rep.cgImage else {
        return []
    }
    var out: [Box] = []
    let req = VNRecognizeTextRequest()
    req.recognitionLevel = .accurate
    req.usesLanguageCorrection = false
    req.recognitionLanguages = ["zh-Hans", "zh-Hant", "en-US"]
    let handler = VNImageRequestHandler(cgImage: cg, options: [:])
    try? handler.perform([req])
    for obs in req.results ?? [] {
        guard let cand = obs.topCandidates(1).first else { continue }
        let r = obs.boundingBox
        out.append(Box(
            path: path,
            text: cand.string,
            x: r.origin.x,
            y: r.origin.y,
            w: r.size.width,
            h: r.size.height,
            conf: Double(cand.confidence)
        ))
    }
    return out
}

var paths: [String] = Array(CommandLine.arguments.dropFirst())
if paths.count == 1, paths[0].hasSuffix(".txt") {
    if let body = try? String(contentsOfFile: paths[0], encoding: .utf8) {
        paths = body.split(whereSeparator: \.isNewline).map(String.init).filter { !$0.isEmpty }
    }
}
var all: [Box] = []
for p in paths {
    all.append(contentsOf: ocr(p))
}
let enc = JSONEncoder()
enc.outputFormatting = [.sortedKeys]
if let data = try? enc.encode(all), let s = String(data: data, encoding: .utf8) {
    print(s)
}
