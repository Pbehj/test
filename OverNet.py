import torch.nn as nn
from ops import *
import torch
import torch.nn.functional as F
import numpy as np

### the new version
class Scale(nn.Module):

    def __init__(self, init_value=1e-3):
        super(Scale, self).__init__()
        self.scale = nn.Parameter(torch.FloatTensor([init_value]))

    def forward(self, input):
        return input * self.scale
        
class Network(nn.Module):

    def __init__(self, **kwargs):
        super(Network, self).__init__()

        wn = lambda x: torch.nn.utils.weight_norm(x)
        upscale = kwargs.get("upscale")
        scale = kwargs.get("scale")
        group = kwargs.get("group", 4)

        self.sub_mean = MeanShift((0.4488, 0.4371, 0.4040), sub=True)
        self.add_mean = MeanShift((0.4488, 0.4371, 0.4040), sub=False)

        self.entry_1 = wn(nn.Conv2d(3, 64, 3, 1, 1))


        self.GDG1 = LDGs(64, 64, wn=wn)
        self.GDG2 = LDGs(64, 64, wn=wn)
        self.GDG3 = LDGs(64, 64, wn=wn)

        self.reduction1 = BasicConv2d(wn, 64*2, 64, 1, 1, 0)
        self.reduction2 = BasicConv2d(wn, 64*3, 64, 1, 1, 0)
        self.reduction3 = BasicConv2d(wn, 64*4, 64, 1, 1, 0)

        self.reduction = BasicConv2d(wn, 64*3, 64, 1, 1, 0)

        self.Global_skip = nn.Sequential(nn.AdaptiveAvgPool2d(1), nn.Conv2d(64, 64, 1, 1, 0), nn.ReLU(inplace=True))

        self.upsample = UpsampleBlock(64, upscale=upscale,  wn=wn, group=group)

        self.exit1 = wn(nn.Conv2d(64, 3, 3, 1, 1))


        self.res_scale = Scale(1)
        self.x_scale = Scale(1)

    def forward(self, x, scale, upscale):
        x = self.sub_mean(x)
        skip = x

        x = self.entry_1(x)

        c0 = o0 = x

        GDG1 = self.GDG1(o0)
        concat1 = torch.cat([c0, GDG1], dim=1)
        out1 = self.reduction1(concat1)

        GDG2 = self.GDG2(out1)
        concat2 = torch.cat([concat1, GDG2], dim=1)
        out2 = self.reduction2(concat2)

        GDG3 = self.GDG3(out2)
        concat3 = torch.cat([concat2, GDG3], dim=1)
        out3 = self.reduction3(concat3)


        output = self.reduction(torch.cat((out1, out2, out3),1))
        output = self.res_scale(output) + self.x_scale(self.Global_skip(x))

        output = self.upsample(output, upscale=upscale)

        output = F.interpolate(output, (x.size(-2) * scale, x.size(-1) * scale), mode='bicubic', align_corners=False)
        skip = F.interpolate(skip, (x.size(-2) * scale, x.size(-1) * scale), mode='bicubic', align_corners=False)

        output = self.exit1(output) + skip
        output = self.add_mean(output)

        return output
