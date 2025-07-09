```
---  
title: my title # Title for the tab in the web browser. The final title will be "{title} - Quantum Benchmark Zoo"  
datatable: true # Set to true if there is at least a datatable in the page  
description: > # Description of the page. Used to set the content of the meta tag used by SEO. Should be one or two sentences with well chosen keywords.  
  Presentation of the awesome protocol blablabla...   
---
```

# Protocol name

## Motivation

- Briefly describe the motivations of the protocol

## Protocol

- Simple description of the protocol. Avoid delving into many technical details.
- Do not hesitate to add pictures. The picture will be redesigned to follow the website theme 
- Use sub-sections if needed

## Assumptions 

- Describe the assumptions of the protocol
- If possible, try to describe the consequences if the assumptions are not respected

## Limitations

- Describe the limitations of the protocol

## Extensions (Facultative)

- Describe the extensions to the protocol (if extensions exist)

## Implementation

- Put links to existing implementation references

## Results

- List of results in the literature that were obtained using the protocol
- For results in tables please directly provide an Excel table. The HTML table will be automatically generated from the Excel table. Tables should be put at the root directory. 
- Graphics will be automatically generated soon

# References

- Generated with the following command: `{% bibliography --cited %}`
- Additional references can be added to the file _bibliography/references.bib. Please avoid duplicates 

# Some extra tips

## Cite references

To cite a reference, add it under the BibTex format in bibliography/references.bib and cite it with its id. The latex reference are rebuilt each time the website is being deployed `{% cite magesan2011scalable %}`

## Latex expressions 
Latex expression are surrounded by `$$`:   
`$$ C_{rand}(n) = \sum_{i=1}^n i \times (1-p^i)p^{i(i-1)/2} $$`

## Datatables
To add a datatable (example here with the Q-score datatable) that is automatically generated.  
The javascript permits to format the table content as latex and to set the default number of items per page.

```
{% include tables/q-score-table.html %}  
<script type="text/javascript"> 
    $(document).ready(function() {
      $('.q-score-table').DataTable(
        {
          "pageLength": 10,
          "drawCallback": function(settings){
           MathJax.Hub.Queue(["Typeset", MathJax.Hub]);ss
          }  
        }  
      );  
    });  
</script>
```

## Images

To add an image, simply use the img tag within a div that centers the content.  
The classes img-small (50% width), img-medium (70% width), img-large (90% width) are only used for devices with more than 769px width.  
Alt expression is really important to improve the indexation of the content.  

```
<div class="center">
  <img src="/img/application-level-benchmark/qBAS-1.png" class="img-medium" alt="Bars and Stripes data set with segmentation of images that are in/outside the set."/> 
</div>
```
