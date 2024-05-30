source := ./basemodel

parent = $(patsubst %/,%,$(dir $1))

MAKEDIR := $(call parent,$(lastword $(MAKEFILE_LIST)))
SRCDIR := $(call parent,$(MAKEDIR))
SCRIPTDIR := $(SRCDIR)
DATADIR := $(SRCDIR)/data
ASSETDIR := $(SRCDIR)/assets

ifndef BASEREPO
$(error BASEREPO is not set)
endif

ifndef AUTHOR
AUTHOR := $(firstword $(subst /, ,$(BASEREPO)))
endif

ifndef BASEMODEL
BASEMODEL := $(notdir $(BASEREPO))
endif

ifndef QUANTMODEL
QUANTMODEL := $(notdir $(abspath .))
endif

ifndef TOASTER_ROOT
$(error TOASTER_ROOT is not set)
endif

export TOASTER_BIN := $(TOASTER_ROOT)/bin
export TOASTER_LIB := $(TOASTER_ROOT)/lib

ifndef ORGANIZATION
ifdef HF_DEFAULT_ORGANIZATION
ORGANIZATION := $(HF_DEFAULT_ORGANIZATION)
else
$(error ORGANIZATION is not set)
endif
endif

mkreadme_opts :=
mkreadme_opts += $(if $(DESCRIPTION),--description $(DESCRIPTION))
mkreadme_opts += $(if $(AUTHOR),--author $(AUTHOR))
mkreadme_opts += $(if $(FULLNAME),--title $(FULLNAME))


QTYPES := IQ1_S IQ1_M IQ2_XXS IQ2_XS IQ2_S IQ2_M Q2_K_S Q2_K
QTYPES += IQ3_XXS IQ3_XS Q3_K_S IQ3_S IQ3_M Q3_K_M Q3_K_L IQ4_XS
QTYPES += Q4_K_S Q4_K_M Q5_K_S Q5_K_M Q6_K Q8_0

QUANTS := $(patsubst %,$(QUANTMODEL).%.gguf,$(QTYPES))
ASSETS := $(notdir $(wildcard $(ASSETDIR)/*.png))
HASHES := $(patsubst %,%.hash,$(QUANTS))

convert_py := convert-hf-to-gguf.py $(if $(PRETOKENIZER),--fallback-pre=$(PRETOKENIZER))
xconvert = python $(TOASTER_BIN)/$1 --outtype=$(or $3,auto) --outfile=$4 $(CONVERT_OPTS) $2
convert = $(call xconvert,$(convert_py),$1,$2,$3)
imatrix_data := $(DATADIR)/20k_random_data.txt
imatrix = $(TOASTER_BIN)/imatrix --chunks $(or $(IMATRIX_CHUNKS),128) -c 128 -m $(filter %.bin,$1) -f $(filter %.txt,$1) -o $2.tmp && mv $2.tmp $2
mkreadme := python $(SCRIPTDIR)/mkreadme.py
quantize = $(TOASTER_BIN)/quantize --imatrix $(filter %.imatrix,$1) $(filter %.bin,$1) $2 $3

all:: quants
bin:: $(QUANTMODEL).bin
imat:: $(QUANTMODEL).imatrix
quants:: assets bin imat
quants:: $(QUANTS)
assets:: $(ASSETS) README.md
hashes:: $(HASHES)

$(QUANTMODEL).bin: | $(source)/$(BASEMODEL)
	$(call convert,$|,$(FTYPE),$@)

$(QUANTS): $(QUANTMODEL).%.gguf:| $(QUANTMODEL).bin $(QUANTMODEL).imatrix
	$(call quantize,$|,$@,$*)

$(HASHES): %.hash: %
	sha256sum $< | cut -f1 -d' ' > $@.tmp && mv -f $@.tmp $@

imatrix_dataset.txt:
	cp $(imatrix_data) $@

%.imatrix: | %.bin imatrix_dataset.txt
	$(call imatrix,$|,$@)

$(ASSETS): %.png: | $(ASSETDIR)/%.png
	cp $| $@

README.md: GNUmakefile
	rm -f $@
	$(mkreadme) $(mkreadme_opts) -o $@ $(BASEREPO)

$(source)/$(BASEMODEL):
	mkdir -p $(@D)
	python $(SCRIPTDIR)/download_model.py $(BASEREPO) $@

.DELETE_ON_ERROR:

clean::
	$(if $(wildcard *.tmp),rm -f *.tmp)
