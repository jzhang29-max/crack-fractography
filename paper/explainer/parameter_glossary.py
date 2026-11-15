"""A plain-English gloss for every constant both detectors read.

Paired with the parameter figure's own table: the name on the left of each entry
is the row label that figure prints, so a reader can hold the two side by side.
build_explainer.py checks the count against the figure's own tally, so a constant
added to the software without a gloss here stops the build.
"""
# One plain-English gloss per constant, in pipeline order. The name on the left is the
# row label the parameters figure uses, so the two can be read side by side.
SEM_GLOSS = [
 ("read the frame", None),
 ("contrast window", "Before anything else the picture is put on a standard brightness scale. The darkest 1% and the brightest 0.5% of pixels are pushed to the ends of the scale, so one stray bright speck cannot decide how bright the whole image looks. Too aggressive and faint cracks are flattened away; too gentle and the image is washed out."),
 ("on 3 named frames", "Three particular frames are read with no clipping at all. They were visibly damaged by the standard setting, so they get the gentler one. This is an exception list, not a rule, and it is on the plate because an undeclared exception is still a setting."),
 ("databar search depth", "Microscopes stamp an information bar along one edge. The software looks for it in the bottom quarter of the frame. Searching further risks mistaking real specimen for the bar."),
 ("databar row window", "How many rows at a time it averages while looking for that bar. Small values are noisy; large ones blur the bar's edge."),
 ("databar sd ratio", "The bar is flatter than the specimen. A row whose variation falls below 40% of typical is a candidate for being bar rather than metal."),
 ("databar mean ratio", "...and its brightness must also differ from typical by this much. Both tests have to agree, so a merely quiet patch of specimen is not mistaken for the bar."),
 ("field-of-view gate", "Anything brighter than 12 of 255 counts as 'inside the imaged field'. Below that is the black surround the instrument writes around the picture."),
 ("field-of-view shrink", "Having found the field, pull the boundary in by 16% so the detector never looks at the soft edge where the image fades out."),
 ("field-of-view floor", "If that shrinking would leave less than a fifth of the frame, something has gone wrong with the detection and the whole frame is kept instead."),
 ("flatten the background", None),
 ("flattening sigma", "The size of the blur used to estimate uneven lighting, in pixels. The blurred copy is subtracted, leaving only local departures. Too small and the crack itself is subtracted away; too large and the shading survives."),
 ("flattening clip", "After subtracting, the result is rescaled using the 0.5th and 99.5th percentiles, for the same reason as the contrast window."),
 ("scale ladder", "The seven blur sizes, from 5 to 320 pixels. A narrow crack only looks dark against its immediate surroundings; a wide one only against a much larger area. One size cannot catch both."),
 ("ladder rungs", "How many sizes are on that ladder. Seven, spaced by doubling."),
 ("decimate above sigma", "Above a blur of 64 pixels the background is estimated on a shrunken copy of the image. At that size the full-resolution calculation costs a great deal of time and changes nothing."),
 ("multiscale union", "Whether to keep a pixel that looks dark at ANY of the seven sizes, rather than at one chosen size. On: measured here as worth +0.025 IoU over the best single size."),
 ("cut the dark pixels", None),
 ("denoise sigma", "A light blur applied just before the decision, to stop single noisy pixels being called cracks. Measured here: the shipped 1.0 is not the best value on the grid."),
 ("MAD multiplier k", "The main dial. A pixel is called crack if it is more than k robust standard deviations darker than typical. Lower k marks more and is less sure; higher k marks less and misses more. This is the one constant in the whole electron arm chosen by testing against hand-marked images."),
 ("darkness gate", "A hard floor: anything darker than 10 of 255 is crack whatever the relative test says. It catches cracks so dark that the local comparison fails. Measured: turning it off halves recall at frame scale."),
 ("clean the cut", None),
 ("opening radius", "Shaves one pixel off every edge and puts it back, which deletes isolated specks without changing anything larger."),
 ("closing radius", "Fills gaps up to 3 pixels, joining a crack that the threshold broke into pieces. Measured here: the shipped 3 is not the best value on the grid."),
 ("connectivity", "Whether two pixels touching only at a corner count as joined. 8 means yes; 4 would mean only edge-sharing counts."),
 ("clean area floor", "Clumps below 13 pixels are deleted at the first pass."),
 ("candidate floor", "Clumps below 40 pixels are deleted at the second. Two floors because the two passes run before and after the gap filling."),
 ("region classifier", "Whether a trained model gets to veto a region. ON in this configuration: it raises precision and costs recall."),
]

TXM_GLOSS = [
 ("the model", None),
 ("recipe", "The name of the fitted configuration currently deployed. Changing it means a different trained model, not a different setting."),
 ("members averaged", "Two models are fitted and their probabilities averaged. Measured: the pair beats either alone."),
 ("feature channels", "How many numbers describe each pixel before the model sees it: brightness, local brightness at several sizes, texture, ridge-likeness and so on."),
 ("backbone", "The large general-purpose image model used, unchanged, to turn image patches into rich descriptions. It was never trained on cracks and is not retrained here."),
 ("SAM tile", "That model cannot read a whole frame; it reads 1024-pixel squares."),
 ("tile stride", "How far it moves between squares. 896 is less than 1024, so neighbouring squares overlap by 128 pixels and the description does not break at the seams."),
 ("embedding stride", "The description comes back coarser than the image, one value per 16 pixels, and is stretched back up."),
 ("the decision", None),
 ("probability threshold", "The averaged probability above which a pixel is called crack. Raising it marks less and is surer."),
 ("correction floor", "Inside an area a person painted as crack, the bar drops to 0.20 instead of being forced on, so the person's stroke means 'believe weaker evidence here' rather than 'this exact brush shape is the answer'."),
 ("SEM k on TXM", "The electron arm's one tuned constant, applied to X-ray images. No value of it works, which is why the two arms are separate."),
 ("clean the mask", None),
 ("speck floor", "Blobs smaller than 2000 pixels are deleted."),
 ("hole fill", "Holes up to 1024 pixels inside a marked region are filled in."),
 ("narrowing window", "The size of the neighbourhood used when trimming a mask back to the width the image actually supports."),
 ("narrowing core", "How confident the centre of a region must be for the trimming to keep it."),
 ("clip to measured width", None),
 ("width clip", "Whether to trim every marked region to the width that can actually be measured in the picture. On."),
 ("clip radius", "How far either side of the crack's centre line the software looks when measuring that width, in pixels."),
 ("clip directions", "How many directions it tries. The narrowest of them is taken as the true across-the-crack width."),
 ("clip probes", "How many points along the crack are measured directly; the rest are filled in from their neighbours."),
 ("clip recentre", "How far the measuring point may slide to sit on the darkest line, in pixels."),
 ("clip peak sigma", "How much darker than the local background a profile must dip before it counts as a real crack edge rather than noise."),
 ("clip background", "Three neighbourhood sizes used to estimate that local background."),
 ("clip min points", "If fewer than 8 points could be measured on a region, the software declines to trim it rather than guessing."),
 ("clip IDW neighbours", "How many measured points are averaged to fill in an unmeasured one."),
 ("reject straight artefacts", None),
 ("straight min area", "Only regions above 200 pixels are considered for rejection."),
 ("straight min aspect", "...and only those at least 6 times longer than they are wide."),
 ("straight max wander", "A region that long and thin is thrown out if its centre line deviates by less than one pixel, because real cracks wander and detector artefacts run dead straight."),
]
